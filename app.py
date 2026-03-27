import warnings
# Ignora warnings que contenham "ScriptRunContext" para limpar o terminal
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")

import streamlit as st
from main import executar_pesquisa
import sys
import re

class StreamlitCapturing:
    def __init__(self, container):
        self.container = container
        self.text = ""

    def write(self, m):
        # Remove códigos de cores ANSI (comum no output do CrewAI)
        clean_text = re.sub(r'\x1b\[[0-9;]*m', '', m)
        self.text += clean_text
        # Atualiza o componente de código no Streamlit em tempo real
        self.container.code(self.text)

    def flush(self):
        pass

    def __enter__(self):
        self._og_stdout = sys.stdout
        sys.stdout = self
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self._og_stdout

def render_help_section():
    """
    Renderiza a seção de ajuda/guia para o usuário final.
    """
    with st.expander("📚 Guia de Uso: O que posso perguntar?", expanded=False):
        st.markdown("""
        ### 🎯 Sobre Esta Ferramenta
        
        Este sistema utiliza **agentes de IA especializados** para analisar dados de e-commerce e responder perguntas em linguagem natural.
        
        Basta digitar sua dúvida abaixo que nossa equipe virtual (Vendas + Financeiro + Logística + Estratégia) irá consultar o banco de dados e entregar uma resposta executiva.
        """)
        
        st.divider()
        
        # =====================================================================
        # BASE DE DADOS DISPONÍVEL
        # =====================================================================
        st.markdown("### 🗄️ Dados Disponíveis para Consulta\n")
        
        col1, col2 = st.columns(2, gap="large")
        
        with col1:
            st.markdown("#### **📦 Vendas & Marketplace**")
            st.markdown("""
            • `vendas_marketplace_amazon`
              - Pedidos, status, canais de venda
              - Produtos (SKU, categoria, tamanho)
              - Valores (amount, currency, qty)
              - Localização (ship_city, ship_state, ship_country)
              - Tipo de cliente (B2B/B2C)
            
            <br>
            
            • `vendas_e_exportacoes_internacionais`
              - Vendas internacionais por cliente
              - Quantidade de peças e valor unitário
              - Valor bruto total por transação
            """, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            st.markdown("#### **🚚 Logística**")
            st.markdown("""
            • `comparativo_de_custos_de_operadores_logisticos`
              - Custos por tipo de serviço:
                - Inbound (recebimento)
                - Outbound (expedição)
                - Armazenagem
              - Comparativo: Shiprocket vs INCREFF
            """)
            
        with col2:
            st.markdown("#### **💰 Financeiro**")
            st.markdown("""
            • `performance_financeira_e_custos_*`
              - Preços de custo (TP) e varejo (MRP)
              - Preços por marketplace (Amazon, Myntra, etc.)
              - Margens por produto/SKU
            
            <br>
            
            • `controle_de_despesas_e_fluxo_de_caixa`
              - Recebimentos e despesas registradas
              - Descrição e valores de cada despesa
              - Fluxo de caixa operacional
            """, unsafe_allow_html=True)
            
        st.write("")
        st.info("💡 **Nota:** Os dados financeiros possuem tabelas separadas por período (ex: maio/2022, março/2021). O sistema identifica automaticamente o período da sua pergunta.")
        
        st.divider()
        
        # =====================================================================
        # EXEMPLOS DE PERGUNTAS POR CATEGORIA
        # =====================================================================
        st.markdown("### 💬 Exemplos de Perguntas\n")
        
        tab_vendas, tab_financeiro, tab_logistica, tab_estrategia = st.tabs([
            "📈 Vendas", "💰 Financeiro", "🚚 Logística", "🎯 Estratégia"
        ])
        
        with tab_vendas:
            st.markdown("""**Perguntas sobre desempenho comercial:**
            
```text
• Qual foi o total de vendas em maio de 2022?
• Quais foram as 5 categorias mais vendidas no último trimestre?
• Qual a % de vendas B2B vs B2C em março de 2021?
• Quanto vendemos para o estado de São Paulo em maio/2022?
• Qual o ticket médio por canal de venda (Amazon vs Merchant)?
• Quantos pedidos foram cancelados em maio de 2022?
• Qual produto (SKU) teve maior volume de vendas?
```""")
            
        with tab_financeiro:
            st.markdown("""**Perguntas sobre resultados e margens:**
            
```text
• Qual foi a margem de lucro líquida em maio de 2022?
• Quais foram as principais despesas operacionais no período?
• Qual o custo médio por produto (TP) nas categorias de vestuário?
• Como está o fluxo de caixa: entradas vs saídas?
• Qual marketplace oferece melhor margem para o SKU XXX?
• Qual a diferença entre MRP original e MRP final após descontos?
• Quanto gastamos com despesas em março de 2021 vs maio de 2022?
```""")
            
        with tab_logistica:
            st.markdown("""**Perguntas sobre custos operacionais:**
            
```text
• Qual operador logístico é mais barato para frete outbound?
• Qual o custo médio de armazenagem por operador?
• Há economia ao trocar de Shiprocket para INCREFF?
• Qual tipo de serviço (Inbound/Outbound) tem maior custo?
• Qual o impacto dos custos logísticos na margem total?
• Existe variação de preço por região de entrega?
```""")
            
        with tab_estrategia:
            st.markdown("""**Perguntas que cruzam múltiplas áreas:**
            
```text
• Qual foi o impacto dos custos logísticos na margem em maio/2022?
• Vale a pena expandir vendas B2B considerando nossa margem atual?
• Quais categorias têm melhor relação volume vs margem?
• Se reduzirmos custos logísticos em 10%, qual o impacto no lucro?
• Quais produtos deveríamos priorizar no próximo trimestre?
• Há oportunidade de economia ao consolidar operadores logísticos?
• Qual a tendência de vendas comparando março/2021 vs maio/2022?
```""")
        
        st.divider()
        
        # =====================================================================
        # DICAS PARA MELHORES RESULTADOS
        # =====================================================================
        st.markdown("### 💡 Dicas para Melhores Respostas\n")
        st.markdown("""
        **1. Seja específico com períodos:**  
        ✅ "Qual foi a margem em **maio de 2022**?"  
        ❌ "Qual foi a margem?" (pode retornar dados misturados)
        
        **2. Mencione a métrica desejada:**  
        ✅ "Qual o **total de vendas brutas** em maio/2022?"  
        ✅ "Qual a **margem líquida %** no período?"
        
        **3. Combine áreas para insights estratégicos:**  
        ✅ "Como os custos logísticos impactaram a margem das vendas B2B?"
        
        **4. Use termos do negócio:**  
        ✅ "SKU", "margem", "B2B", "marketplace", "frete outbound"
        
        **5. Peça comparações quando útil:**  
        ✅ "Compare a margem de março/2021 com maio/2022"
        """)
        
        st.write("")
        
        with st.warning("⚠️ **Limitações a Considerar**"):
            st.markdown("""
            • **Períodos disponíveis:** Os dados financeiros estão organizados por tabelas mensais (ex: maio/2022, março/2021). Perguntas sobre períodos não cobertos podem retornar informações parciais.
            
            • **Dados logísticos:** A tabela de operadores não possui campo de data. Os valores são de referência e podem não corresponder exatamente ao período da sua análise de vendas.
            
            • **Moedas:** Todas as análises financeiras consideram a moeda registrada. Caso haja múltiplas moedas, especifique se deseja conversão ou filtro.
            
            • **Tempo de resposta:** Análises complexas que cruzam múltiplas tabelas podem levar 30-90 segundos para serem processadas.
            
            • **Validação de segurança:** Todas as respostas passam por validação automática para garantir conformidade e precisão.
            """)
        
        st.divider()
        
        st.markdown("### 🚀 Quer testar agora?\n")
        exemplos_rapidos = [
            "Qual foi o total de vendas brutas em maio de 2022?",
            "Qual a margem de lucro líquida no período de maio/2022?",
            "Qual operador logístico é mais econômico para frete outbound?",
            "Qual foi o impacto dos custos logísticos na margem em maio/2022?",
            "Quais foram as 3 categorias mais rentáveis em maio/2022?"
        ]
        
        for exemplo in exemplos_rapidos:
            if st.button(f"💬 {exemplo[:60]}...", key=f"ex_{hash(exemplo)}"):
                # Compatibilizando o botão com o chat_input do layout
                st.session_state.messages.append({"role": "user", "content": exemplo})
                st.rerun()

# Configuração da página e visual
st.set_page_config(
    page_title="Analytics Agent - E-commerce",
    page_icon="🤖",
    layout="centered"
)

st.title("📊 Painel Inteligente (Agent E-commerce)")
st.caption("Pergunte ao C-Level (Equipe de Estratégia, Vendas, Logística e Finanças) sobre seus dados baseados no banco SQLite.")

# Inicializar o histórico do chat na sessão ANTES do render_help_section
if "messages" not in st.session_state:
    st.session_state.messages = []

render_help_section()

st.sidebar.title("⚙️ Configurações")
mostrar_logs = st.sidebar.toggle("Exibir pensamentos da IA", value=False, help="Ative para exibir a caixa preta detalhando o raciocínio dos agentes do CrewAI durante a execução.")

st.sidebar.divider()

if st.session_state.messages:
    # Formata o histórico atual do chat como texto para exportação
    historico_texto = " Histórico de Análise - AI Analytics C-Level\n\n"
    
    for m in st.session_state.messages:
        papel = "VOCÊ" if m["role"] == "user" else "SISTEMA (AGENTE)"
        historico_texto += f"[{papel}]:\n{m['content']}\n\n{'-'*60}\n\n"
        
    st.sidebar.download_button(
        label="📥 Exportar Conversa",
        data=historico_texto,
        file_name="analise_historico_chat.txt",
        mime="text/plain",
        help="Baixe todo o histórico do chat atual em um arquivo de texto (.txt)."
    )

# Exibir histórico de chat existente
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Obter nova entrada do usuário pelo campo de texto
if prompt := st.chat_input("Ex: Qual foi o impacto da logística na margem de lucro?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()  # Reinicia a tela para atualizar o chat e disparar a lógica abaixo

# Se a última mensagem do histórico for do usuário, significa que precisamos gerar resposta
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    
    pergunta_atual = st.session_state.messages[-1]["content"]
    
    # Area do assistente responder
    with st.chat_message("assistant"):
        
        if mostrar_logs:
            # Roda com captura de logs em tempo real
            with st.status("🤖 Agentes analisando dados...", expanded=True) as status:
                log_placeholder = st.empty()
                
                with StreamlitCapturing(log_placeholder):
                    try:
                        historico_passado = st.session_state.messages[:-1]
                        resposta = executar_pesquisa(
                            pergunta_usuario=pergunta_atual, 
                            historico=historico_passado,
                            verbose=True
                        )
                        status.update(label="✅ Análise concluída!", state="complete", expanded=False)
                    except Exception as e:
                        st.error(f"Ocorreu um erro técnico: {e}")
                        resposta = None
        else:
            # Roda silenciosamente e mais limpo
            with st.spinner("🤖 Agentes processando silenciosamente..."):
                try:
                    historico_passado = st.session_state.messages[:-1]
                    resposta = executar_pesquisa(
                        pergunta_usuario=pergunta_atual, 
                        historico=historico_passado,
                        verbose=False
                    )
                except Exception as e:
                    st.error(f"Ocorreu um erro técnico: {e}")
                    resposta = None

        # Exibe a resposta final formatada (Markdown) enviada pelo Diretor de Estratégia
        if resposta:
            st.markdown(resposta)
            st.session_state.messages.append({"role": "assistant", "content": resposta})
            st.rerun() # Força rerun para limpar carregamentos da tela e fixar a mensagem
