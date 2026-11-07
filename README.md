# SGGD — Backend (Django)

Sistema de Gestão e Gratificação de Desempenho da **Secretaria de Saúde do Recife (SESAU)**. O recorte desta entrega é a avaliação de **gestores, supervisores e coordenadores**, utilizando como referência operacional a planilha **CAM 1.2** fornecida à equipe. Não calcula gratificações dos demais profissionais por exercerem atividades assistenciais.

> **Atenção às fontes:** “CAM 1.2” é a identificação da planilha recebida, não o nome oficial da portaria. A **Portaria Conjunta SESAU/SEPLAGTD nº 001, de 30/08/2024**, publicada no Diário Oficial nº 131 em 21/09/2024 (pp. 5–10), fundamenta parte das regras. Não foi comprovada a vigência atual da versão nem a equivalência integral entre planilha e portaria. Divergências estão identificadas e cálculos duvidosos não devem ser usados como resultados oficiais.

## Situação do desenvolvimento (07/11/2026)

| Componente | Estado | O que existe |
| --- | --- | --- |
| `acesso` | Implementado e testado | Login por e-mail/senha, sessão e CSRF; grupos, permissões e rotas protegidas. |
| `cadastro` | Implementado e testado | Distritos, tipos de unidade, unidades, categorias, avaliados, responsabilidades e API administrativa. |
| `normativa` | Modelos e importação testados | CAM 1.2 carregada, catálogo hierárquico, pesos, metas e regras; serviço de cálculo isolado. |
| `coleta` | Pendente | Lançamento de resultados e homologação por competência. |
| `apuracao` | Pendente | Orquestração dos resultados, consolidação por gestor e memória de cálculo. |
| `publicacao`, `recurso`, `pagamento`, `auditoria` | Não entregues funcionalmente neste recorte | Módulos previstos na arquitetura original; implementação futura conforme escopo. |

Os testes locais das três primeiras áreas foram **executados e confirmados pela equipe**. O catálogo da Normativa está configurado no banco, mas **não existe ainda apuração ponta a ponta** de gratificação.

## Requisitos e preparação

- Python **3.12 ou superior**, Django **5.2**, Django REST Framework **3.16** e PostgreSQL; as faixas efetivas de dependências estão em `requirements.txt`.
- Ambiente virtual (`.venv`) e banco PostgreSQL configurado no `.env` a partir de `.env.example`.
- Não comitar o `.env` nem senhas de teste.

No PowerShell, a partir da pasta do backend (onde fica `manage.py`):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Configure .env e crie o banco PostgreSQL antes de prosseguir.
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Painel técnico: <http://127.0.0.1:8000/admin/>. A criação de usuários funcionais no Django Admin ainda depende de ajustes no formulário de criação por e-mail; durante os testes, foram utilizados usuários criados por script local. **Não inserir senhas simples no repositório.**

## Organização do projeto

```text
apps/
├── acesso/       # Autenticação, autorização e interface de permissões
├── cadastro/     # Estrutura organizacional, avaliados e responsabilidades
├── normativa/    # Catálogo CAM 1.2, regras, pesos e cálculos isolados
├── coleta/       # Pendente
├── apuracao/     # Pendente
├── auditoria/    # Pendente
├── publicacao/   # Pendente
├── recurso/      # Pendente
└── pagamento/    # Pendente
sggd/              # Configuração e URLs do projeto Django
```

Os apps compartilham **um único banco PostgreSQL**; o `import-linter` verifica os contratos de importação definidos no repositório. Outros componentes devem consumir a interface pública de `cadastro` (`apps.cadastro.interface`) quando essa interface atender à consulta necessária.

## Controle de Acesso (`apps/acesso`)

O login utiliza **e-mail**, sessões Django e CSRF. Rotas:

- `GET /api/auth/csrf/` — define cookie CSRF;
- `POST /api/auth/login/` — login com e-mail e senha;
- `GET /api/auth/me/` — sessão, grupos, permissões e `is_superuser`;
- `POST /api/auth/logout/` — encerra a sessão.

Grupos reais: **Configurador**, **Registrador**, **Homologador** e **Consultador**. `is_superuser` é administração técnica, não um quinto papel funcional. Os grupos recebem permissões do catálogo `apps.acesso.models.Operacao`; autorização deve ser verificada no backend, não apenas ocultando menus no React. O escopo por unidade/indicador ainda será validado nas APIs futuras.

Não confundir esses **papéis de acesso** com as **categorias de avaliação** da CAM 1.2 (USF, GG, SNA etc.).

## Cadastro (`apps/cadastro`)

Modelos: `Distrito`, `TipoUnidade`, `Unidade`, `CategoriaAvaliacao`, `PessoaAvaliada`, `Responsabilidade`.

- A migração inicial cria **8 distritos**, **7 tipos de unidade** e **11 categorias** (7 de unidade e 4 distritais); não cria pessoas nem unidades fictícias.
- `PessoaAvaliada` é independente de `Usuario` (associação opcional).
- Uma `Responsabilidade` associa a pessoa a **uma unidade OU um distrito**, sua categoria e um período. Para múltiplas unidades, existem múltiplos vínculos. O gestor distrital se vincula ao distrito, sem replicar cada unidade.
- Validações impedem período inválido, escopo incompatível e sobreposição da mesma pessoa/categoria/destino.
- API administrativa: `/api/cadastro/distritos/`, `/tipos-unidade/`, `/unidades/`, `/categorias-avaliacao/`, `/avaliados/`, `/responsabilidades/` (todos sob `/api/cadastro/`).
- O Django Admin oferece as telas de manutenção; **não há ainda telas React de Cadastro**.

O Cadastro **não armazena metas ou pesos**. Mudanças de distrito/unidade no futuro devem preservar o retrato organizacional das avaliações já encerradas — snapshot de apuração ainda não implementado.

## Normativa CAM 1.2 (`apps/normativa`)

Modelos: `VersaoNormativa`, `Indicador` (estrutura pai/filho), `RegraIndicador` (meta, método, periodicidade e parâmetros por categoria), `PesoIndicador` (peso por categoria).

**Carga validada pela equipe:** 58 registros hierárquicos (57 da planilha + 1 raiz auxiliar do indicador 4), 44 pesos principais, 157 associações de regras e 11 categorias. O catálogo abrange **cinco indicadores principais**: medicamentos/MMH, gestão do trabalho, satisfação do usuário, desempenho da unidade e vigilância em saúde distrital.

Importadores idempotentes (sem sobrescrever regras divergentes) e modo `--dry-run`:

```powershell
python manage.py importar_cam12 --dry-run
python manage.py importar_cam12
python manage.py configurar_regras_cam12 --dry-run
python manage.py configurar_regras_cam12
```

Os dados dos importadores estão em `apps/normativa/data/cam12.json` e `regras_cam12.json`. Os comandos ficam em `apps/normativa/management/commands/`. A lógica matemática isolada está em `apps/normativa/services/calculo_cam12.py`.

As regras importadas incluem situações marcadas **`CALCULAVEL`**, **`ENTRADA_TRATADA`** e **`REVISAR`**. Há 127 associações com métodos de cálculo suportados a partir de dados já aferidos, 11 que requerem notas previamente tratadas e 19 sinalizadas para revisão. Regras `REVISAR` **não devem ser calculadas automaticamente**. Não executar código arbitrário vindo de JSON; o serviço usa operações predeterminadas.

Pendências conhecidas: pesos internos da satisfação (80/20 na portaria versus indicação excepcional 100/0 na planilha), composição da ESF (70/30 na portaria versus pesos divergentes na planilha), classificação de item UCIS/MAC, variantes MAC conforme serviços oferecidos e resultados pré-processados de áreas técnicas. A Portaria determina redistribuição proporcional quando um indicador não puder ser aferido por motivo técnico/administrativo (art. 8º); isso é diferente de **nota zero** ou **dado ausente**.

A Normativa está disponível no **Django Admin**. **Não existe ainda `/api/normativa/` nem formulário React para gerenciar regras.** O serviço de cálculo não consulta sozinho os dados das unidades nem gera avaliações completas.

## Testes e verificação

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test apps.acesso apps.cadastro apps.normativa
python -m unittest apps.normativa.test_motor_cam12_puro
lint-imports
```

**Ordem para reconstruir a base em um ambiente novo:** criar DB e `.env` → `migrate` → `importar_cam12` → `configurar_regras_cam12`. Não repita `makemigrations` se o esquema já corresponde aos arquivos versionados; o comando com `--check --dry-run` apenas verifica desvios.

## Limites do MVP e próximo desenvolvimento

O objetivo é **avaliar e consolidar pontuações** dos gestores, supervisores e coordenadores. Estão fora desta entrega: cálculo monetário final/folha, integração automática com Hórus, SISAB e demais fontes, CAM 2.0 completa, motor genérico de fórmulas e recursos eletrônicos (a portaria cita o SEI/RECIFE).

**Próxima etapa: `coleta`**, para informar dados e notas da competência com fonte, autoria, estado e posterior homologação; em seguida, `apuracao` realizará a agregação entre unidades/distritos, usará regras validadas e registrará a memória dos cálculos. Nenhum resultado gerado nesta fase deve ser tratado como valor oficial de gratificação.

## Documentação

- `docs/SGGD_Escopo_CAM_1_2_Atualizado.docx` — decisão de escopo, referências e estado atual.
- `docs/SGGD_Componente_Cadastro.docx` — modelos, responsabilidades, validações e limites.
- `docs/SGGD_Componente_Normativa_CAM12.docx` — catálogo, importadores, regras e restrições.
- `docs/SGGD_Componente_Cadastro.docx` — Papeise autenticação
