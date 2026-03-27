# 📊 Painel Inteligente E-commerce (C-Level Agents)

Bem-vindo ao **Painel Inteligente E-commerce**, um assistente virtual movido a Inteligência Artificial, desenhado para funcionar como se você tivesse uma equipe executiva completa trabalhando para você 24 horas por dia.

O objetivo deste painel é permitir que você faça perguntas em texto normal (como estivesse mandando uma mensagem de WhatsApp) sobre seus dados de e-commerce, finanças, vendas e logística, e receba respostas estratégicas mastigadas diretamente do seu banco de dados.

---

![CrewAI agent workflow visualization showing intelligent decision routing and sequential agent execution in a dark-themed dashboard interface](crewai%20agent.gif)

---

## 🚀 Como Funciona a Magia? (Estratégia dos Agentes)

No lugar de usarmos apenas um "ChatGPT" que tenta adivinhar tudo sozinho, construímos uma **Equipe de Especialistas** utilizando a tecnologia do *CrewAI*. O diferencial do projeto é o uso de um fluxo inteligente de decisão e execução:

1. 🎯 **O Diretor de Estratégia (O Roteador):**
   Ele é o primeiro a ler sua pergunta. Ele analisa o contexto e o histórico da conversa para decidir o caminho mais eficiente:

   * **Rota Rápida:** Se a pergunta for apenas uma continuidade do que já foi dito ou não exigir novos dados, ele responde diretamente usando a memória do chat.
   * **Rota de Análise:** Se ele identificar a necessidade de números exatos, ele aciona o fluxo completo de especialistas.
2. ⚙️ **Execução Multidisciplinar Sequencial:**
   Quando a análise é necessária, os agentes não trabalham isoladamente. Eles operam em um **processo sequencial**:

   * **Analista de Vendas:** Extrai o volume e transações dos marketplaces.
   * **Analista de Logística:** Calcula os custos de frete e operação com base nos parceiros (Shiprocket/INCREFF).
   * **Analista Financeiro:** Cruza as vendas com os custos para extrair a margem de lucro e P&L.
   * **Diretor de Estratégia:** Recebe os relatórios de todos os acima para criar a síntese final que você vê na tela.
3. 🛡️ **O Auditor de Segurança (Guardrails):**
   Antes de você receber a resposta, este agente revisa o texto final. Ele garante que não houve "alucinações" numéricas, que a linguagem é profissional e que nenhum dado sensível foi exposto. Se algo estiver errado, ele solicita a reescrita automática antes da entrega.

Todo esse processo de coordenação garante que a resposta não seja apenas um "palpite", mas um relatório consolidado baseado em fatos do seu banco de dados.

---

## 🗄️ Dados Disponíveis para a Equipe

A base de dados é real e o sistema só lê os espaços configurados. Eles conseguem tirar insights sobre:

* Transações da Amazon (Status, Categorias dos Produtos, Localização e Valores).
* Tabela de Fluxo de Caixa (Despesas x Receitas por período).
* Margem de custo versus preço de varejo.
* Operadores Logísticos e tabelas de frete da Índia/Internacional.

*(Nota: O banco de dados utilizado funciona atravéz de um arquivo leve local SQLite chamado `ecommerce_analytics.db` que fica na pasta `data`)*

---

## ⚙️ Como Instalar e Rodar o Projeto

Caso queira executar este painel no seu computador, aqui está o passo a passo simplificado, mesmo que você não seja programador:

### Passo 1: Preparar o Ambiente

É necessário ter a linguagem **Python 3.10.0** instalada na sua máquina. Abra o terminal (Prompt de Comando ou PowerShell) dentro da pasta base deste projeto e instale os pacotes (ferramentas) que o sistema requer.

Basta rodar o comando:

```bash
pip install -r requirements.txt
```

### Passo 2: Gerar a Base de Dados

Antes da Inteligência Artificial funcionar, ela precisa de dados! É necessário gerar o seu banco `sqlite` local pela primeira vez.
Para isso, basta abrir o arquivo chamado `01.ingestao_dos_dados.ipynb` (usando o VS Code ou o Jupyter) e rodar as células de código dele ("Run All"). Ele se encarregará de baixar as planilhas da nuvem, limpar tudo, criar a pasta `data` (se ela não existir) e gerar o arquivo de banco de dados perfeito para a IA consumir.

### Passo 3: Validar Chaves de Segurança

O projeto se conecta a robôs na nuvem (Databricks / Anthropic / Meta/ Bedrock/ Azure OpenAI/ Vertex AI). Por questões de segurança, arquivos de senha não vêm baixados junto com a pasta original. Você deve **criar manualmente** os seguintes arquivos de texto na raiz do projeto:

- `API_KEY.txt`: Crie um arquivo em branco com este nome exato e cole seu token de acesso em formato JSON (exemplo: `{"KEY": "sua-senha-aqui", "URL": "seu-link-aqui"}`).
- `config_modelos.txt`: Dizendo qual versão de IA cada funcionário é (se este não estiver na pasta, basta criá-lo com a estrutura de modelos padrão).

### Passo 4: Inicializar a Interface Gráfica

Agora a mágica acontece. O jeito mais fácil de rodar o aplicativo é simplesmente dar um **duplo clique** no arquivo executável `iniciar_painel.bat` que está dentro da pasta!

Isso abrirá a tela do terminal sozinha e já subirá a interface maravilhosamente bem.

*(Se preferir usar linha de código manuais, você também pode abrir o terminal e digitar `streamlit run app.py`)*

### Passo 5: Faça o Teste!

Isso abrirá uma janela automática no seu Google Chrome ou Edge. O painel estará com um Toggle (botão de ligar/desligar no canto) de *"Exibir pensamentos da IA"*:

- Se você quiser ver as planilhas cruzando código "como no Matrix", ligue.
- Se você quiser só o visual limpo no modo chefe, desligue!

Utilize os botões prontos ("Exemplos Rápidos") para brincar com os dados.

---

*Desenhado com foco em Governança, Decisão Estratégica e Roteamento Sustentável de Inteligência Artificial.*
