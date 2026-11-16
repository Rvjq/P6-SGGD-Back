# SGGD — Backend Django

Backend do **Sistema de Gestão e Gratificação de Desempenho (SGGD)**, protótipo acadêmico voltado à coleta, revisão e futura apuração dos indicadores dos **gestores, supervisores e coordenadores** da Secretaria de Saúde do Recife (SESAU).

O recorte funcional é a **CAM 1.2**, conforme planilha disponibilizada à equipe. A Portaria Conjunta SESAU/SEPLAGTD nº 001, de 30/08/2024 (Diário Oficial do Recife nº 131, 21/09/2024), é uma das referências. **Não foi comprovado que a planilha corresponde integralmente à portaria ou que suas regras estejam vigentes hoje.** O protótipo não produz resultado oficial de gratificação.

## Tecnologias

Python, **Django 5.2**, Django REST Framework 3.16, PostgreSQL, Psycopg 3 e `import-linter`. Dependências e limites de versão em `requirements.txt`. O frontend React + TypeScript está no repositório separado `P6-SGGD-Front`.

## Componentes e estado atual

| Componente | Disponível | Limite atual |
| --- | --- | --- |
| `acesso` | Login por e-mail, sessão/CSRF, quatro papéis, permissões, consulta de usuários e administração restrita de contas operacionais | Configurador não pode criar superusuários ou alterar contas privilegiadas |
| `cadastro` | Distritos, tipos e unidades, categorias, pessoas avaliadas, responsabilidades com vigência, APIs de cadastro e consulta | Pessoa avaliada não é necessariamente usuário do sistema |
| `normativa` | Catálogo CAM 1.2, hierarquia de indicadores, metas/regras, pesos, importadores e funções de cálculo isoladas | Regras divergentes/indefinidas permanecem pendentes |
| `coleta` | Competências mensais, autorizações, tarefas guiadas, rascunhos, envio, homologação, painéis de progresso | Ainda não efetua a apuração das notas individuais |
| `apuracao` | Estrutura do app | Fluxo de apuração CAM 1.2 **não implementado** |
| `auditoria`, `publicacao`, `recurso`, `pagamento` | Estrutura dos apps | Fora do fluxo operacional desta versão |

### Conceitos essenciais

- **Usuário:** pessoa com login e papéis de **Configurador**, **Registrador**, **Homologador** ou **Consultador**.
- **Pessoa avaliada:** gestor, supervisor ou coordenador; pode existir sem login.
- **Responsabilidade:** vínculo, com início e fim de vigência, entre pessoa avaliada e **uma unidade OU um distrito**.
- **Categoria de avaliação:** para uma unidade, decorre do **tipo de unidade**; para o distrito, da função do gestor (`GG`, `SNA`, `SNB1`, `SNB2`). Não é um grupo de login.
- **Coleta:** armazena informações dos indicadores de uma unidade ou distrito, sem duplicar dados para cada gestor.
- **Apuração:** etapa futura que usará os dados homologados para avaliar cada pessoa conforme sua categoria.

## Preparar o ambiente

Em `P6-SGGD-Back`, configure um PostgreSQL local e copie os valores apropriados de `.env.example` para `.env` (não versionar). No PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py check
python manage.py runserver
```

`DJANGO_SECRET_KEY` é obrigatório. Use `DJANGO_DEBUG=1` apenas em desenvolvimento. Se necessário, crie o administrador **técnico** com `python manage.py createsuperuser`. **Não conceda `is_staff` ao Configurador** apenas para ele usar suas telas; suas operações usam APIs próprias.

## Comando único para a base Recife / CAM 1.2

```powershell
python manage.py preparar_base_recife --dry-run
python manage.py preparar_base_recife
```

Prepara de forma idempotente **8 distritos, 7 tipos de unidade, 11 categorias de avaliação**, o catálogo de **58 registros hierárquicos**, **44 pesos principais** e **157 associações de regras**. Reutiliza os importadores de `apps.normativa` sem duplicá-los nem alterar registros divergentes.

Opções de manutenção: `--apenas-estrutura` e `--atualizar-rotulos`. Para executar isoladamente as cargas da Normativa:

```powershell
python manage.py importar_cam12 --dry-run
python manage.py importar_cam12
python manage.py configurar_regras_cam12 --dry-run
python manage.py configurar_regras_cam12
```

Os cinco indicadores principais são **Medicamentos/MMH, Gestão do Trabalho, Satisfação do Usuário, Desempenho da Unidade e Vigilância em Saúde**. Casos marcados para revisão não devem gerar nota automática nem nota zero.

## Criar dados fictícios para testes

A massa **DEMO** não faz parte da base normativa. Depois da preparação, com `DJANGO_DEBUG=1`:

```powershell
python manage.py gerar_mock_recife --dry-run
python manage.py gerar_mock_recife
```

Por padrão gera até **21 unidades fictícias** (três de cada tipo), **53 pessoas avaliadas** e suas **53 responsabilidades** (21 de unidade e 32 distritais: quatro categorias para cada um dos oito distritos). Esses dados possuem identificadores de demonstração e não sobrescrevem registros reais conflitantes. A quantidade efetiva pode ser menor conforme a situação do banco.

Opções úteis:

```powershell
python manage.py gerar_mock_recife --unidades-por-tipo 5
python manage.py gerar_mock_recife --sem-distritais
python manage.py limpar_mock_recife --dry-run
python manage.py limpar_mock_recife --confirmar
```

Esses comandos **não criam logins, competências nem atribuições de Registradores**. A limpeza é explícita e respeita os vínculos protegidos. Não execute os mocks em produção.

## Fluxo de Coleta e avaliação

1. **Configurador** abre o período mensal, cadastra pessoas avaliadas e responsabilidades e distribui unidades/distritos aos Registradores.
2. O **backend** gera tarefas a partir da competência, do escopo, da categoria e da Normativa. Para o distrito, o **Indicador 5** só é solicitado quando existe alguma responsabilidade distrital vigente cuja categoria o exige. Vários gestores elegíveis compartilham o mesmo lançamento técnico.
3. **Registrador** navega por **período → distrito → unidade/distrito → indicador**, preenche subindicadores, salva rascunhos e envia os dados com indicação da fonte.
4. **Homologador** aprova ou devolve com justificativa; não pode homologar os próprios dados.
5. **Apuração (futura)** consolidará os indicadores e os pesos por categoria e os relacionará às pessoas responsáveis na competência.

Unidade sem responsável cadastrado deve aparecer como **pendência de configuração**, sem bloquear a coleta. Regra não aferível permanece **indisponível**, nunca convertida em zero por padrão.

## Principais rotas REST

| Endereço | Finalidade |
| --- | --- |
| `/api/auth/csrf/`, `/login/`, `/me/`, `/logout/` | Autenticação e sessão (todas sob `/api/auth/`) |
| `/api/auth/usuarios/`, `/api/auth/operadores/` | Consulta de usuários e gerenciamento limitado de contas operacionais |
| `/api/cadastro/` | Distritos, categorias, tipos, unidades, avaliados e responsabilidades |
| `/api/cadastro/painel/` | Consulta consolidada do Cadastro |
| `/api/normativa/versoes/` | Consulta das versões normativas e respectivos detalhes |
| `/api/coleta/competencias/` | Períodos de avaliação |
| `/api/coleta/autorizacoes/` | Autorizações para lançamento |
| `/api/coleta/tarefas/`, `/tarefas/salvar/`, `/tarefas/enviar/` | Tarefas, rascunhos e envio (sob `/api/coleta/`) |
| `/api/coleta/tarefas/revisao/`, `/tarefas/decidir/` | Revisão e homologação (sob `/api/coleta/`) |
| `/api/coleta/resumo/` | Painel operacional |
| `/api/coleta/painel-configurador/` | Contadores administrativos e progresso por Registrador |
| `/admin/` | Django Admin de uso **técnico** |

Todas as operações relevantes exigem autenticação e checagem de permissões no servidor; menus no frontend não substituem autorização.

## Testes

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test apps.acesso apps.cadastro apps.normativa apps.coleta
lint-imports
```

Testes focados:

```powershell
python manage.py test apps.cadastro.test_comandos_recife
python manage.py test apps.coleta.test_i5_distrital_condicional
python manage.py test apps.coleta.test_rota_painel_configurador
```

## Limites do protótipo

- **Apuração, notas finais dos gestores, pagamento e integrações externas:** ainda não implementados de ponta a ponta.
- **CAM 1.2:** algumas regras têm divergências entre planilha e portaria; não apresentar tais resultados como oficiais.
- **Atribuições de Coleta:** ainda não possuem vigência por competência; a abrangência dos Homologadores também demanda refinamento.
- **Dados sensíveis:** não compartilhar `.env`, `.venv/`, dump de banco ou usuários/senhas reais em pacotes de revisão.

**Documentação revisada em 16/11/2026**, conforme o estado atual dos componentes Acesso, Cadastro, Normativa e Coleta.
