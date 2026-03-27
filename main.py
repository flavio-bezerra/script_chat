import os
import sys
import ast
import json
import re
import logging
import warnings
from pathlib import Path
from typing import Optional, Dict, Any

from langchain_community.utilities import SQLDatabase
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool

# Ignora warnings que contenham "ScriptRunContext"
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")

# CONFIGURAÇÃO INICIAL

# Configuração de logging estruturado
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# CONFIGURAÇÕES GLOBAIS

# Caminho base do projeto (cross-platform: Windows, Linux, macOS)
PROJECT_ROOT = Path(__file__).parent
DB_PATH = Path(os.getenv("DB_PATH", PROJECT_ROOT / "data" / "ecommerce_analytics.db"))

# Tabelas esperadas no banco de dados
EXPECTED_TABLES = [
    "vendas_marketplace_amazon",
    "vendas_e_exportacoes_internacionais",
    "performance_financeira_e_custos_maio_2022",
    "performance_financeira_e_custos_marco_2021",
    "controle_de_despesas_e_fluxo_de_caixa",
    "comparativo_de_custos_de_operadores_logisticos",
]

# CONFIGURAÇÕES PADRÃO (Fallback se arquivos não existirem)

CONFIG_PADRAO_MODELOS = {
    'modelos': {
        'estrategista': 'databricks-claude-sonnet-4-6',
        'analista': 'databricks-claude-haiku-4-5',
        'guardrails': 'databricks-meta-llama-3-1-8b-instruct',
    },
    'parametros': {
        'estrategista': {'temperature': 0.25, 'max_tokens': 8000, 'timeout': 120},
        'analista': {'temperature': 0.1, 'max_tokens': 4000, 'timeout': 60},
        'guardrails': {'temperature': 0.0, 'max_tokens': 500, 'timeout': 30},
    },
    'crew': {
        'max_iter': 3,
        'max_rpm': 10,
        'max_retries': 2,
    }
}

# BACKSTORIES COMO CONSTANTES (Organização + Reuso)

BACKSTORY_ANALISTA = """
Você é um Analista de Dados especializado em e-commerce. 
Seu foco é extrair insights precisos das tabelas de vendas e operações.

📋 Tabelas principais:
• vendas_marketplace_amazon: order_id, date, status, sku, category, qty, amount, ship_country, is_b2b
• vendas_e_exportacoes_internacionais: date, customer_name, sku, qty_pieces, unit_rate, gross_amount

⚠️  Regras:
• Use apenas sintaxe SQLite
• Para datas: strftime('%Y-%m', date) = '2022-05' para filtrar maio/2022
• Sempre valide números com COUNT() antes de SELECT *
• Considere apenas pedidos com status='Shipped' para métricas de venda
• Use a tool 'Obter Schema da Tabela' se tiver dúvida sobre colunas
"""

BACKSTORY_FINANCEIRO = """
Como CFO Analítico, você é rigoroso com números e focado em P&L.

📋 Tabelas principais:
• performance_financeira_e_custos_maio_2022: sku, tp_price, mrp_old, final_mrp_old, [marketplaces]
• controle_de_despesas_e_fluxo_de_caixa: received_date, expense_description, expense_amount

💰 Fórmulas-chave:
• Margem Bruta = (receita_liquida - cogs) / receita_liquida * 100
• Receita Líquida = SUM(amount) - descontos - devoluções
• Sempre confirme a moeda (currency) antes de somar valores
• Use a tool 'Obter Schema da Tabela' se tiver dúvida sobre colunas
"""

BACKSTORY_LOGISTICA = """
Especialista em Supply Chain e custos logísticos.

📋 Tabela principal:
• comparativo_de_custos_de_operadores_logisticos: service_type, shiprocket_rate, increff_rate

🚚 Foco:
• Compare operadores por tipo de serviço (Inbound/Outbound/Armazenagem)
• Identifique oportunidades de economia sem comprometer SLA
• Se não houver data na tabela, informe valores de referência
• Use a tool 'Obter Schema da Tabela' se tiver dúvida sobre colunas
"""

BACKSTORY_DIRETOR = """
Você é o Diretor de Estratégia de um e-commerce em crescimento.

🎯 Seu papel:
• Ouvir os especialistas (vendas, financeiro, logística)
• Conectar os pontos entre métricas operacionais e resultados financeiros
• Entregar conclusões acionáveis para a diretoria

✍️  Estilo de resposta:
• Seja objetivo: executivos precisam de clareza, não de rodeios
• Baseie-se em dados: cite números exatos quando possível
• Termine com recomendação: "Próximo passo sugerido: ..."
• NÃO invente dados - use apenas o que foi reportado pela equipe
"""

BACKSTORY_GUARDRAILS = """
Você é um validador especializado em IA responsável. 
Sua função NÃO é gerar conteúdo, mas SIM revisar respostas.

🔍 Checklist OBRIGATÓRIO:
1. 🚫 Linguagem preconceituosa? (raça, gênero, religião, orientação, deficiência, etc.)
2. 🚫 Dados pessoais expostos? (CPF, e-mail, telefone, endereço completo)
3. 🚫 Afirmações não suportadas pelos dados? (alucinações numéricas ou factuais)
4. 🚫 Recomendações ilegais, antiéticas ou fora de compliance?
5. ✅ Tom profissional, claro e adequado para contexto executivo?

📋 Formato de saída OBRIGATÓRIO (JSON válido):
{"status": "APPROVED" | "REJECTED", "reason": "motivo ou null", "suggestion": "sugestão ou null"}

Exemplo aprovado: {"status": "APPROVED", "reason": null, "suggestion": null}
Exemplo rejeitado: {"status": "REJECTED", "reason": "Menção a dado pessoal", "suggestion": "Remover e-mail do texto"}
"""

# CARREGAMENTO DE ARQUIVOS DE CONFIGURAÇÃO (Formato Original)

def load_config_file(filepath: str, default: Dict[str, Any]) -> Dict[str, Any]:
    """
    Carrega configuração de arquivo .txt no formato de dicionário Python.
    Usa ast.literal_eval() para segurança (não executa código arbitrário).
    
    Args:
        filepath: Caminho para o arquivo de configuração.
        default: Valores padrão se o arquivo não existir ou falhar.
    
    Returns:
        Dict com as configurações carregadas ou padrão.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            config = ast.literal_eval(f.read())
        
        if not isinstance(config, dict):
            raise ValueError("Formato inválido: o arquivo deve conter um dicionário Python")
        
        logger.info(f"✅ Configurações carregadas de '{filepath}'")
        return config
        
    except FileNotFoundError:
        logger.warning(f"⚠️  Arquivo '{filepath}' não encontrado. Usando configurações padrão.")
        return default
        
    except (SyntaxError, ValueError) as e:
        logger.error(f"❌ Erro ao parsear '{filepath}': {e}")
        logger.warning("⚠️  Usando configurações padrão como fallback.")
        return default


def load_credentials(filepath: str = "API_KEY.txt") -> Dict[str, str]:
    """
    Carrega credenciais do arquivo no formato original:
    {'KEY': 'sua-chave', 'URL': 'https://seu-endpoint'}
    
    Args:
        filepath: Caminho para o arquivo de credenciais.
    
    Returns:
        Dict com chaves 'KEY' e 'URL'.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            credencial = ast.literal_eval(f.read())
        
        # Validação básica
        if not isinstance(credencial, dict) or "KEY" not in credencial or "URL" not in credencial:
            raise ValueError("Formato inválido no arquivo de credenciais")
        
        logger.info(f"✅ Credenciais carregadas de '{filepath}'")
        return credencial
        
    except FileNotFoundError:
        logger.warning(f"⚠️  Arquivo '{filepath}' não encontrado. Usando credenciais padrão.")
        return {"KEY": "DEFAULT_TOKEN", "URL": "DEFAULT_URL"}
        
    except (SyntaxError, ValueError) as e:
        logger.error(f"❌ Erro ao parsear credenciais: {e}")
        return {"KEY": "DEFAULT_TOKEN", "URL": "DEFAULT_URL"}


# FERRAMENTAS (TOOLS) — Escopo do Módulo

# Referência global para o database
_db_instance: Optional[SQLDatabase] = None


def get_db_instance() -> SQLDatabase:
    """Retorna a instância global do database."""
    if _db_instance is None:
        raise RuntimeError("Database não inicializado. Chame load_database() primeiro.")
    return _db_instance


@tool("Consulta SQL")
def db_tool(query: str) -> str:
    """
    Executa consultas SQL no banco de dados SQLite.
    
    ⚠️  Apenas consultas SELECT são permitidas por segurança.
    ⚠️  Use sintaxe compatível com SQLite.
    ⚠️  Para datas, use formatos: 'YYYY-MM-DD' ou 'MM/DD/YYYY'.
    
    Args:
        query: Query SQL para execução.
    
    Returns:
        Resultado da consulta como string ou mensagem de erro.
    """
    try:
        query_upper = query.strip().upper()
        
        # Segurança: bloqueia operações de escrita
        if not query_upper.startswith(("SELECT", "WITH", "PRAGMA table_info")):
            return "❌ Erro: Apenas consultas SELECT, WITH ou PRAGMA são permitidas."
        
        # Prevenção: alerta para queries sem LIMIT
        if "SELECT " in query_upper and "LIMIT" not in query_upper and "*" in query:
            logger.warning("⚠️  Query sem LIMIT detectada. Adicione LIMIT para evitar travamentos.")
        
        db = get_db_instance()
        return db.run(query)
        
    except Exception as e:
        logger.error(f"❌ Erro na execução da query: {e}")
        return f"❌ Erro ao executar consulta: {str(e)}"


@tool("Obter Schema da Tabela")
def get_table_schema(table_name: str) -> str:
    """
    Retorna a estrutura (colunas e tipos) de uma tabela específica.
    
    Args:
        table_name: Nome exato da tabela no banco de dados.
    
    Returns:
        Descrição do schema da tabela ou mensagem de erro.
    """
    try:
        db = get_db_instance()
        return db.get_table_info([table_name])
    except Exception as e:
        logger.error(f"❌ Erro ao obter schema de '{table_name}': {e}")
        return f"❌ Erro: {str(e)}"


# FUNÇÕES DE INFRAESTRUTURA

def load_database(config: dict) -> SQLDatabase:
    """
    Inicializa a conexão com o banco de dados e valida tabelas.
    
    Args:
        config: Configurações contendo a URI do banco.
    
    Returns:
        Instância do SQLDatabase inicializada.
    
    Raises:
        ConnectionError: Se falhar ao conectar ou validar tabelas.
    """
    global _db_instance
    
    try:
        # Valida existência do arquivo
        if not DB_PATH.exists():
            raise FileNotFoundError(f"Arquivo do banco não encontrado: {DB_PATH}")
        
        # Conecta ao banco
        db_uri = f"sqlite:///{DB_PATH.resolve()}"
        db = SQLDatabase.from_uri(db_uri, engine_args={"connect_args": {"check_same_thread": False}})
        
        # Valida tabelas esperadas
        available_tables = db.get_usable_table_names()
        missing_tables = set(EXPECTED_TABLES) - set(available_tables)
        
        if missing_tables:
            logger.warning(f"⚠️  Tabelas ausentes no banco: {missing_tables}")
            logger.info(f"✅ Tabelas disponíveis: {available_tables}")
        else:
            logger.info(f"✅ Todas as tabelas esperadas estão presentes")
        
        # Teste rápido de conexão
        db.run("SELECT 1")
        
        _db_instance = db
        logger.info("✅ Database conectado com sucesso")
        return db
        
    except Exception as e:
        logger.error(f"❌ Falha ao conectar com o banco: {e}")
        raise ConnectionError(f"Erro de conexão com o banco de dados: {e}")


def create_llms_by_role(credenciais: Dict[str, str], config_modelos: Dict[str, Any]) -> Dict[str, LLM]:
    """
    Cria instâncias de LLM otimizadas por função do agente.
    
    Args:
        credenciais: Dict com 'KEY' e 'URL' para autenticação.
        config_modelos: Dict com configurações de modelos e parâmetros.
    
    Returns:
        dict com chaves: 'estrategista', 'analista', 'guardrails'
    """
    llms = {}
    
    modelos = config_modelos.get('modelos', CONFIG_PADRAO_MODELOS['modelos'])
    parametros = config_modelos.get('parametros', CONFIG_PADRAO_MODELOS['parametros'])
    
    # 🧠 LLM para Diretor de Estratégia (raciocínio complexo)
    llms['estrategista'] = LLM(
        model=modelos.get("estrategista", CONFIG_PADRAO_MODELOS['modelos']['estrategista']),
        api_key=credenciais["KEY"],
        base_url=credenciais["URL"],
        temperature=parametros.get("estrategista", {}).get("temperature", 0.25),
        max_tokens=parametros.get("estrategista", {}).get("max_tokens", 8000),
        timeout=parametros.get("estrategista", {}).get("timeout", 120),
        max_retries=3,
    )
    
    # 📊 LLM para Analistas (tarefas estruturadas + precisão)
    llms['analista'] = LLM(
        model=modelos.get("analista", CONFIG_PADRAO_MODELOS['modelos']['analista']),
        api_key=credenciais["KEY"],
        base_url=credenciais["URL"],
        temperature=parametros.get("analista", {}).get("temperature", 0.1),
        max_tokens=parametros.get("analista", {}).get("max_tokens", 4000),
        timeout=parametros.get("analista", {}).get("timeout", 60),
        max_retries=3,
    )
    
    # 🛡️ LLM para Guardrails (validação rápida + barata)
    llms['guardrails'] = LLM(
        model=modelos.get("guardrails", CONFIG_PADRAO_MODELOS['modelos']['guardrails']),
        api_key=credenciais["KEY"],
        base_url=credenciais["URL"],
        temperature=parametros.get("guardrails", {}).get("temperature", 0.0),
        max_tokens=parametros.get("guardrails", {}).get("max_tokens", 500),
        timeout=parametros.get("guardrails", {}).get("timeout", 30),
        max_retries=2,
    )
    
    logger.info(
        f"✅ LLMs carregados: "
        f"Estrategista={modelos.get('estrategista')}, "
        f"Analista={modelos.get('analista')}, "
        f"Guardrails={modelos.get('guardrails')}"
    )
    
    return llms


# DEFINIÇÃO DOS AGENTES

def create_agents(db: SQLDatabase, llms: Dict[str, LLM]) -> Dict[str, Agent]:
    """Cria agentes usando LLMs especializados por função."""
    
    # 📊 Analista de Vendas
    analista_vendas = Agent(
        role="Analista de Vendas Sênior",
        goal="Analisar métricas de vendas com precisão técnica.",
        backstory=BACKSTORY_ANALISTA,
        verbose=False,
        allow_delegation=False,
        tools=[db_tool, get_table_schema],
        llm=llms['analista'],
    )

    # 💰 Analista Financeiro
    analista_financeiro = Agent(
        role="Analista Financeiro (CFO)",
        goal="Avaliar desempenho financeiro com rigor numérico.",
        backstory=BACKSTORY_FINANCEIRO,
        verbose=False,
        allow_delegation=False,
        tools=[db_tool, get_table_schema],
        llm=llms['analista'],
    )

    # 🚚 Analista de Logística
    analista_logistica = Agent(
        role="Analista de Logística",
        goal="Mapear custos operacionais e identificar economias.",
        backstory=BACKSTORY_LOGISTICA,
        verbose=False,
        allow_delegation=False,
        tools=[db_tool, get_table_schema],
        llm=llms['analista'],
    )

    # 🧠 Diretor de Estratégia
    diretor_estrategia = Agent(
        role="Diretor de Estratégia",
        goal="Sintetizar análises e gerar insights executivos acionáveis.",
        backstory=BACKSTORY_DIRETOR,
        verbose=False,
        allow_delegation=True,
        llm=llms['estrategista'],
    )

    # 🛡️ Guardrails Agent
    guardrails_agent = Agent(
        role="Validador de Conformidade e Ética",
        goal="Garantir que todas as respostas sejam seguras, imparciais e adequadas.",
        backstory=BACKSTORY_GUARDRAILS,
        verbose=False,
        allow_delegation=False,
        llm=llms['guardrails'],
    )

    return {
        "vendas": analista_vendas,
        "financeiro": analista_financeiro,
        "logistica": analista_logistica,
        "estrategia": diretor_estrategia,
        "guardrails": guardrails_agent,
    }


# DEFINIÇÃO DAS TASKS

def create_tasks(agents: Dict[str, Agent], periodo: Optional[Dict[str, int]] = None) -> list:
    """
    Cria as tasks da equipe parametrizadas por período.
    
    Args:
        agents: Dicionário com os agentes criados.
        periodo: Dict com 'mes' e 'ano' para filtrar análises (default: maio/2022).
    
    Returns:
        Lista de Tasks configuradas.
    """
    periodo = periodo or {"mes": 5, "ano": 2022}
    periodo_str = f"{periodo['mes']:02d}/{periodo['ano']}"
    date_filter = f"strftime('%Y-%m', date) = '{periodo['ano']}-{periodo['mes']:02d}'"
    
    task_vendas = Task(
        description=(
            f"📊 ANALISE DE VENDAS - Período {periodo_str}\n\n"
            f"Use o filtro de  {date_filter}\n\n"
            f"Entregáveis:\n"
            f"1. Total de vendas brutas (SUM de amount/gross_amount)\n"
            f"2. Quantidade de pedidos únicos (COUNT DISTINCT order_id)\n"
            f"3. Top 3 categorias por receita\n"
            f"4. % de vendas B2B vs B2C\n\n"
            f"⚠️  Considere apenas pedidos com status='Shipped' ou similares."
        ),
        expected_output=(
            f"Resumo executivo de vendas para {periodo_str} com: "
            f"valor total, volume de pedidos, mix de categorias e canal. "
            f"Inclua números exatos extraídos do banco."
        ),
        agent=agents["vendas"],
    )

    task_logistica = Task(
        description=(
            f"🚚 CUSTOS LOGÍSTICOS - Período {periodo_str}\n\n"
            f"Consulte a tabela 'comparativo_de_custos_de_operadores_logisticos'.\n\n"
            f"Entregáveis:\n"
            f"1. Custo médio por tipo de serviço (Inbound/Outbound/Armazenagem)\n"
            f"2. Comparativo Shiprocket vs INCREFF por serviço\n"
            f"3. Estimativa de custo total de frete no período (se houver dados)\n\n"
            f"💡 Se não houver data na tabela logística, informe os valores de referência."
        ),
        expected_output=(
            f"Detalhamento dos custos logísticos para {periodo_str}: "
            f"valores por operador, tipo de serviço e recomendação de economia."
        ),
        agent=agents["logistica"],
    )

    task_financeiro = Task(
        description=(
            f"💰 ANÁLISE FINANCEIRA - Período {periodo_str}\n\n"
            f"Use as tabelas de performance e controle de despesas.\n\n"
            f"Entregáveis:\n"
            f"1. Receita líquida total (após descontos)\n"
            f"2. Custos diretos (TP/COGS) e despesas operacionais\n"
            f"3. Margem de lucro bruta e líquida (% e valor absoluto)\n"
            f"4. Principais itens de despesa do período\n\n"
            f"💰 Fórmula margem: (receita_liquida - custos) / receita_liquida * 100"
        ),
        expected_output=(
            f"Análise financeira para {periodo_str} com: receita, custos, "
            f"despesas e margens. Destaque pontos de atenção ou oportunidade."
        ),
        agent=agents["financeiro"],
    )

    task_estrategia = Task(
        description=(
            f"🎯 SÍNTESE EXECUTIVA - Período {periodo_str}\n\n"
            f"Com base nos relatórios de vendas, logística e finanças gerados, "
            f"responda de forma objetiva e baseada em dados à pergunta do usuário.\n\n"
            f"❓ Pergunta: {{pergunta_usuario}}\n\n"
            f"📋 Estrutura da resposta:\n"
            f"1. Resumo dos achados principais (1 parágrafo)\n"
            f"2. Dados-chave que sustentam a conclusão (números exatos)\n"
            f"3. Recomendação acionável ou próximo passo sugerido\n\n"
            f"⚡ Seja direto: executivos precisam de clareza, não de rodeios."
        ),
        expected_output=(
            "Resposta executiva final, com 3-5 parágrafos, respondendo diretamente "
            "à pergunta do usuário com dados consolidados e recomendação clara."
        ),
        agent=agents["estrategia"],
        context=[task_vendas, task_logistica, task_financeiro],
    )

    return [task_vendas, task_logistica, task_financeiro, task_estrategia]


def create_guardrails_task(guardrails_agent: Agent, task_estrategia: Task) -> Task:
    """Task de validação final com saída estruturada em JSON."""
    
    return Task(
        description=(
            "🔐 VALIDAÇÃO FINAL DE SEGURANÇA E CONFORMIDADE\n\n"
            "Você deverá analisar rigorosamente a resposta gerada pelo Diretor de Estratégia "
            "que lhe é passada como contexto, antes da entrega ao usuário.\n\n"
            "🔍 Checklist de validação:\n"
            "1. Há linguagem discriminatória ou preconceituosa?\n"
            "2. Há exposição de dados pessoais (PII: CPF, e-mail, telefone)?\n"
            "3. Há afirmações numéricas não suportadas pelos dados do banco?\n"
            "4. Há recomendações que violam leis, políticas ou ética?\n"
            "5. O tom é profissional e adequado para contexto executivo?\n\n"
            "✅ Se TODOS os itens OK: status='APPROVED'\n"
            "❌ Se QUALQUER item falhar: status='REJECTED' + explicação\n\n"
            "⚠️  SAÍDA OBRIGATÓRIA - JSON VÁLIDO:\n"
            '{"status": "APPROVED", "reason": null, "suggestion": null}\n'
            "OU\n"
            '{"status": "REJECTED", "reason": "Motivo específico", "suggestion": "Como corrigir"}'
        ),
        expected_output=(
            "JSON válido com exatamente 3 chaves: status (string), reason (string ou null), "
            "suggestion (string ou null). Sem texto adicional antes ou depois do JSON."
        ),
        agent=guardrails_agent,
        context=[task_estrategia],
    )


# UTILITÁRIOS

def parse_guardrails_output(raw_output: str) -> Dict[str, Any]:
    """
    Extrai JSON do output do guardrails, mesmo se vier com markdown ou texto extra.
    
    Returns:
        dict com status, reason, suggestion ou dict de erro se falhar.
    """
    try:
        # Tenta parse direto primeiro
        return json.loads(raw_output.strip())
    except json.JSONDecodeError:
        pass
    
    try:
        # Tenta extrair JSON de dentro do texto
        json_match = re.search(r'\{[\s\S]*"status"[\s\S]*\}', raw_output)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        logger.warning(f"⚠️  Falha ao parsear output do guardrails: {e}")
    
    # Fallback seguro: rejeita se não conseguir parsear
    return {
        "status": "REJECTED",
        "reason": "Falha ao validar formato da resposta (JSON inválido)",
        "suggestion": "Re-gerar resposta com formato JSON válido"
    }


def validacao_pre_llm(texto: str) -> Dict[str, Any]:
    """
    Validações rápidas com regex antes de chamar o LLM guardrails.
    Filtra casos óbvios de PII e termos proibidos.
    """
    problemas = []
    
    # 🚫 PII básico (CPF, e-mail, telefone brasileiro)
    if re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', texto):
        problemas.append("Possível CPF detectado")
    if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', texto):
        problemas.append("Possível e-mail detectado")
    if re.search(r'\(?\d{2}\)?[\s-]?9?\d{4}[\s-]?\d{4}', texto):
        problemas.append("Possível telefone detectado")
    
    # 🚫 Lista de termos sensíveis (expanda conforme necessidade)
    termos_proibidos = []  # Adicione termos específicos da sua organização
    
    if any(termo in texto.lower() for termo in termos_proibidos):
        problemas.append("Linguagem inadequada detectada")
    
    if problemas:
        return {
            "status": "REJECTED",
            "reason": "; ".join(problemas),
            "suggestion": "Remover dados sensíveis ou linguagem inadequada"
        }
    
    return {"status": "APPROVED", "reason": None, "suggestion": None}

# FUNÇÃO PRINCIPAL COM GUARDRAILS

def executar_pesquisa(
    pergunta_usuario: str, 
    historico: Optional[list] = None,
    periodo: Optional[Dict[str, int]] = None,
    verbose: bool = True,
    usar_guardrails: bool = True
) -> str:
    """
    Função principal: executa a análise completa via CrewAI com validação de segurança.
    
    Args:
        pergunta_usuario: Pergunta em linguagem natural a ser respondida.
        periodo: Dict opcional com {'mes': int, 'ano': int} para filtrar análise.
        verbose: Se True, habilita logs detalhados do CrewAI.
        usar_guardrails: Se True, valida resposta com agente de segurança.
    
    Returns:
        String com a resposta executiva gerada pelos agentes.
    
    Raises:
        ValueError, ConnectionError: Em caso de falhas de configuração ou conexão.
    """
    try:
        # 1. Carrega credenciais (formato original)
        logger.info("🔄 Carregando credenciais de API_KEY.txt...")
        credenciais = load_credentials(str(PROJECT_ROOT / "API_KEY.txt"))
        
        # Validação de credenciais
        if credenciais["KEY"] == "DEFAULT_TOKEN":
            logger.warning("⚠️  Usando credenciais padrão. Configure API_KEY.txt para produção.")
            return (
                "🚨 **ATENÇÃO: Arquivo de Senha Ausente!** 🚨\n\n"
                "Parece que o arquivo `API_KEY.txt` não foi encontrado na raiz do projeto. "
                "Para que os agentes de IA consigam pensar e analisar seus dados, "
                "é necessário conectar o sistema à nuvem fornecendo a sua chave de acesso.\n\n"
                "**Passo a passo para criá-lo:**\n\n"
                "1. Abra a pasta principal deste projeto (onde está o arquivo `app.py`).\n"
                "2. Crie um novo arquivo de texto vazio e dê o nome exato de **`API_KEY.txt`**.\n"
                "3. Abra esse arquivo, copie e cole o seu token pessoal de API respeitando o formato JSON abaixo:\n"
                "   ```json\n"
                "   {\"KEY\": \"sua-senha-aqui\", \"URL\": \"seu-link-aqui\"}\n"
                "   ```\n"
                "4. Salve e feche o arquivo de texto.\n"
                "5. Volte aqui no painel e tente fazer sua pergunta novamente!"
            )
        
        # 2. Carrega configurações de modelos
        logger.info("🔄 Carregando configurações de modelos...")
        config_modelos = load_config_file(str(PROJECT_ROOT / "config_modelos.txt"), CONFIG_PADRAO_MODELOS)
        
        # 3. Conecta ao banco de dados
        logger.info("🔄 Conectando ao banco de dados...")
        db = load_database({})
        
        # 4. Inicializa LLMs por função
        logger.info("🔄 Inicializando LLMs especializados...")
        llms = create_llms_by_role(credenciais, config_modelos)
        
        # 5. Cria agentes
        logger.info("🔄 Criando agentes especializados...")
        agents = create_agents(db, llms)
        
        # 6. Cria tasks parametrizadas
        logger.info(f"🔄 Configurando tasks para período {periodo or 'default'}...")
        tasks_principais = create_tasks(agents, periodo)
        task_estrategia = tasks_principais[-1]
        
        # 7. Adiciona task de guardrails se habilitado
        tasks_completas = tasks_principais.copy()
        task_guardrails = None
        if usar_guardrails:
            logger.info("🛡️  Task de guardrails habilitada")
            task_guardrails = create_guardrails_task(agents["guardrails"], task_estrategia)
            tasks_completas.append(task_guardrails)
        
        historico_str = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in (historico or []) if msg.get("role") != "system"])
        historico_context = f"\n\nHistórico da Conversa:\n{historico_str}\n\n" if historico_str else ""
        
        # ROTEAMENTO (Decide se precisa rodar os outros agentes de BD)
        needs_sql = True
        if historico_str:
            logger.info("🔀 Avaliando necessidade de SQL (Router)...")
            router_task = Task(
                description=f"Histórico:\n{historico_str}\n\nNova Pergunta: {pergunta_usuario}\n\nEssa pergunta EXIGE extrair novos números no banco de dados (SIM) ou é apenas continuidade/cumprimento da conversa com os diretores (NÃO)? Responda apenas 'SIM' ou 'NÃO'.",
                expected_output="'SIM' ou 'NÃO'",
                agent=agents["estrategia"]
            )
            r_crew = Crew(agents=[agents["estrategia"]], tasks=[router_task], verbose=False)
            rota = str(r_crew.kickoff()).strip().upper()
            if "N" in rota and "S" not in rota:
                needs_sql = False
                logger.info("⏩ Rota Rápida: Ignorando SQL e respondendo via histórico.")

        if not needs_sql:
            # Rota Rápida: apenas Estrategista usando histórico
            chat_task = Task(
                description=f"{historico_context}O usuário fez um follow-up: {pergunta_usuario}\nResponda mantendo o contexto da conversa e seu perfil como Diretor.",
                expected_output="Resposta direta ao usuário com base na conversa anterior.",
                agent=agents["estrategia"]
            )
            chat_crew = Crew(agents=[agents["estrategia"]], tasks=[chat_task], verbose=verbose)
            chat_crew.kickoff()
            resposta_estrategia = str(chat_task.output.raw) if hasattr(chat_task.output, "raw") else str(chat_task.output)
            # Ignora task_guardrails forte na rota rápida para simplificar
            task_guardrails = None 
            
        else:
            # 8. Monta e executa o Crew completo
            logger.info("🚀 Iniciando execução do Crew completo...")
            crew_config = config_modelos.get('crew', CONFIG_PADRAO_MODELOS['crew'])
            
            # Atualiza a task do estrategista com a memória curta embutida nativamente pro contexto visual
            task_estrategia.description = f"{historico_context}" + task_estrategia.description
            
            crew = Crew(
                agents=list(agents.values()),
                tasks=tasks_completas,
                process=Process.sequential,
                verbose=verbose,
                memory=True, # Habilitando a memória implícita do CrewAI conforme solicitado
                max_iter=crew_config.get("max_iter", 3),
                max_rpm=crew_config.get("max_rpm", 10),
            )
            
            # Executa com inputs parametrizados
            crew.kickoff(inputs={"pergunta_usuario": pergunta_usuario})
            
            # 9. Processa resultado
            resposta_estrategia = str(task_estrategia.output.raw) if hasattr(task_estrategia.output, "raw") else str(task_estrategia.output)
        
        # 10. Validação guardrails
        if usar_guardrails and task_guardrails:
            logger.info("🔐 Executando validação de segurança...")
            
            # Validação pré-LLM (rápida)
            validacao_pre = validacao_pre_llm(resposta_estrategia)
            if validacao_pre["status"] == "REJECTED":
                logger.warning(f"❌ Bloqueado na validação pré-LLM: {validacao_pre['reason']}")
                return f"⚠️  A resposta gerada contém conteúdo inadequado: {validacao_pre['reason']}"
            
            # Validação via LLM guardrails
            if hasattr(task_guardrails, 'output') and task_guardrails.output:
                validacao_raw = str(task_guardrails.output.raw) if hasattr(task_guardrails.output, "raw") else str(task_guardrails.output)
                validacao_dict = parse_guardrails_output(validacao_raw)
                
                if validacao_dict.get("status") == "APPROVED":
                    logger.info("✅ Resposta aprovada pelo guardrails")
                else:
                    logger.warning(f"❌ Resposta rejeitada: {validacao_dict.get('reason')}")
                    return (
                        f"{resposta_estrategia}\n\n"
                        f"⚠️  Aviso de Validação: {validacao_dict.get('reason')}\n"
                        f"💡 Sugestão: {validacao_dict.get('suggestion')}"
                    )
            else:
                logger.warning("⚠️  Output do guardrails não disponível, pulando validação LLM")
        
        logger.info("✅ Análise concluída com sucesso!")
        return resposta_estrategia
        
    except (ValueError, ConnectionError) as e:
        logger.error(f"❌ Erro de configuração/conexão: {e}")
        return f"⚠️  Erro de configuração: {str(e)}"
        
    except Exception as e:
        logger.exception(f"❌ Erro inesperado na execução: {e}")
        return (
            "⚠️  Ocorreu um erro ao processar sua solicitação. "
            "Verifique os logs para detalhes ou tente novamente."
        )

# ENTRY POINT (EXECUÇÃO DIRETA)

if __name__ == "__main__":
    print("="*80)
    print("🚀 CREWAI ANALYTICS PARA E-COMMERCE")
    print("="*80)
    
    # Pergunta de teste
    pergunta_teste = (
        "Qual foi o impacto dos custos logísticos na nossa margem de lucro em maio de 2022? "
        "Haveria economia ao trocar de operador?"
    )
    
    print(f"\n❓ PERGUNTA: {pergunta_teste}\n")
    print("🔍 Executando análise completa (vendas + financeiro + logística + guardrails)...\n")
    
    # Executa com guardrails habilitado
    resposta = executar_pesquisa(
        pergunta_usuario=pergunta_teste,
        periodo={"mes": 5, "ano": 2022},
        verbose=True,       # Mude para False em produção
        usar_guardrails=True  # Mude para False se quiser pular validação
    )
    
    print("\n" + "="*80)
    print("📋 RESPOSTA EXECUTIVA:")
    print("="*80)
    print(resposta)
    print("="*80)
    print("✅ Análise concluída!")