# hein IDE — Plano de arquitetura do login e do fluxo GitHub

## 1. Objetivo deste documento

Este documento descreve, antes de qualquer nova implementação, como funciona
atualmente a autenticação GitHub da hein IDE, por que existem três telas no
painel Git, por que a tela de boas-vindas criou uma segunda entrada para o
GitHub e como o fluxo deve ser reorganizado sem quebrar os seguintes cenários:

- usuário que não quer entrar no GitHub ao abrir a IDE;
- usuário que entra no GitHub na tela de boas-vindas;
- usuário que abre um projeto local e só depois decide entrar no GitHub;
- usuário que troca de conta enquanto um projeto está aberto;
- usuário que trabalha apenas com Git local;
- usuário que clona repositórios públicos;
- usuário que clona repositórios privados;
- usuário que publica, envia, atualiza e vincula um projeto.

**Estado deste documento:** proposta para análise.  
**Importante:** a implementação descrita aqui ainda não deve ser iniciada
automaticamente. Primeiro a arquitetura deve ser revisada e aprovada.

---

## 2. Regras que não podem ser alteradas

1. A hein IDE é uma aplicação 100% desktop em Python + PySide6.
2. Não transformar o projeto em aplicação web, mobile ou serviço HTTP.
3. Git local e GitHub remoto são capacidades diferentes.
4. O usuário pode trabalhar sem autenticação GitHub.
5. Login GitHub deve ser opcional no início da IDE.
6. O usuário deve poder autenticar-se depois de abrir um projeto.
7. O token nunca deve aparecer:
   - na interface;
   - em logs;
   - em mensagens de erro;
   - na URL exibida ao usuário;
   - nos argumentos visíveis de um processo.
8. A autenticação deve continuar usando o Device Flow do GitHub.
9. A sessão deve continuar centralizada em `git_config.py`.
10. Não devem existir duas implementações diferentes para clonar repositórios
    privados.
11. A venv da IDE não pode ser confundida com a venv do projeto do usuário.
12. Alterações fora do escopo de login, conta, repositórios e clone não fazem
    parte desta proposta.

---

## 3. Estrutura atual relevante

```text
hein-basic/
├── main.py
├── _APP_/
│   ├── Boas_Vindas/
│   │   ├── janela_picker.py
│   │   ├── dialogo_novo_projeto.py
│   │   └── lancador_projeto.py
│   └── main_window/
│       └── ...
├── _PAINEL_ESQUERDO_/
│   └── Git/
│       ├── a__git_ui_entrar.py
│       ├── b__git_ui_conta.py
│       ├── c__git_ui_projeto/
│       │   ├── __init__.py
│       │   ├── _projeto.py
│       │   ├── _paineis_status_diff.py
│       │   ├── _paineis_branches_guardados.py
│       │   └── _paineis_historico.py
│       ├── git_ui.py
│       ├── git_autentica.py
│       ├── git_config.py
│       ├── git_api.py
│       ├── git_gerente.py
│       ├── git_terminal.py
│       └── git_ui_utils.py
└── nucleo/
    └── ...
```

---

## 4. Componentes compartilhados atuais

### 4.1 `git_config.py`

Arquivo:

```text
_PAINEL_ESQUERDO_/Git/git_config.py
```

É o armazenamento local da sessão GitHub. A configuração é mantida em:

```text
%APPDATA%\hein\github_config.json
```

O objeto singleton é obtido por:

```python
config_github()
```

Ele mantém:

- token da sessão ativa;
- login da conta ativa;
- nome da conta;
- lista de contas salvas;
- conta ativa;
- projetos recentes.

Principais operações:

```python
config_github().token
config_github().login
config_github().nome
config_github().esta_logado()
config_github().registrar_sessao(...)
config_github().ativar_conta(login)
config_github().limpar_sessao()
config_github().contas()
```

Esse arquivo é a fonte única da sessão. Nenhuma tela deve manter uma sessão
paralela ou salvar outro token em outro arquivo.

### 4.2 `git_autentica.py`

Arquivo:

```text
_PAINEL_ESQUERDO_/Git/git_autentica.py
```

Responsável pelo GitHub OAuth Device Flow:

1. solicita um código de dispositivo;
2. mostra o código para o usuário;
3. abre a página do GitHub;
4. consulta periodicamente se o usuário autorizou;
5. recebe o token;
6. consulta os dados da conta;
7. chama `config.registrar_sessao(...)`.

O objeto principal é:

```python
GerenciadorAuth
```

Essa lógica deve continuar existindo em um único lugar. As telas devem
solicitar autenticação, mas não devem reimplementar o Device Flow.

### 4.3 `git_api.py`

Arquivo:

```text
_PAINEL_ESQUERDO_/Git/git_api.py
```

Responsável pelas chamadas à API REST do GitHub, usando o token da sessão:

- buscar o usuário;
- listar repositórios;
- criar repositórios;
- verificar repositórios.

A API e o comando local `git` são camadas diferentes. Uma chamada autenticada
à API não significa que o processo `git clone` esteja autenticado.

### 4.4 `git_gerente.py`

Arquivo:

```text
_PAINEL_ESQUERDO_/Git/git_gerente.py
```

Responsável pelas operações locais do Git:

- detectar Git;
- inicializar repositório;
- verificar `.git`;
- adicionar e remover remoto;
- status;
- add;
- commit;
- push;
- pull;
- clone;
- branches;
- histórico;
- restauração.

Esse arquivo deve ser a camada única para operações do Git local. A UI não
deve montar comandos Git diferentes para a mesma operação.

---

## 5. Como o painel Git antigo funciona hoje

### 5.1 Orquestrador `git_ui.py`

Arquivo:

```text
_PAINEL_ESQUERDO_/Git/git_ui.py
```

O `PainelGitHub` cria as três telas sempre:

```python
self._tela_entrar  = GitUIEntrar(self._terminal)
self._tela_conta   = GitUIConta(self._terminal)
self._tela_projeto = GitUIProjeto(self._terminal)
```

Depois coloca as três em um `QStackedWidget`.

Índices atuais:

```text
0 — GitUIEntrar
1 — GitUIConta
2 — GitUIProjeto
```

Ao construir o painel:

- se `config_github().esta_logado()` for verdadeiro, mostra a tela B;
- se não houver sessão, mostra a tela A.

### 5.2 Tela A — `a__git_ui_entrar.py`

Responsabilidade atual:

- exibir a tela de login;
- iniciar o Device Flow;
- exibir o código;
- abrir `github.com/login/device`;
- aguardar a confirmação;
- informar que o login foi concluído;
- mandar o orquestrador para a tela B.

O componente interno `_PainelDeviceFlow` é a parte visual do processo.

A tela A é uma tela de autenticação, não uma tela de projeto.

### 5.3 Tela B — `b__git_ui_conta.py`

Responsabilidade atual:

- mostrar a conta autenticada;
- trocar entre contas salvas;
- adicionar outra conta;
- sair da conta;
- criar novo projeto;
- publicar o projeto atual;
- baixar/clonar projeto;
- criar repositório no GitHub.

Essa tela acabou acumulando responsabilidades de dois momentos diferentes:

1. gerenciamento de conta antes de abrir um projeto;
2. operações de publicação e download de projetos.

O menu de contas da tela B usa:

```python
config_github().contas()
config_github().ativar_conta(login)
```

O botão de baixar da tela B usa atualmente:

```python
GerenciadorGit.baixar_projeto(url, destino, token)
```

Esse é um dos pontos que precisa ser revisto porque existe outro fluxo de clone
na tela de boas-vindas.

### 5.4 Tela C — `c__git_ui_projeto`

Arquivo principal:

```text
_PAINEL_ESQUERDO_/Git/c__git_ui_projeto/_projeto.py
```

Responsabilidade atual:

- representar o projeto aberto;
- mostrar o nome do projeto;
- mostrar branch e último commit;
- informar se existe remoto;
- abrir o GitHub no navegador;
- trocar o remoto;
- desvincular remoto;
- apagar remoto, quando permitido;
- abrir a aba completa do Git;
- salvar commit;
- enviar;
- atualizar;
- abrir histórico.

A tela C é a tela correta para as operações do projeto aberto.

Problema atual: quando o projeto está aberto e não há conta ativa, a tela C não
oferece um caminho claro para iniciar o login. Ela possui ações que dependem
de token, mas o acesso visível ao Device Flow está no painel A/B.

---

## 6. Como a tela de boas-vindas funciona hoje

Arquivo:

```text
_APP_/Boas_Vindas/janela_picker.py
```

A tela de boas-vindas é aberta no boot sem projeto.

Ela já possui:

- projetos recentes;
- abrir projeto;
- abrir arquivo;
- escolha do local dos projetos;
- opção de criar `.venv`;
- seleção de interpretador Python;
- criação de novo projeto;
- campo para colar URL;
- clone de repositório;
- botão para carregar repositórios GitHub;
- lista de repositórios públicos e privados recebidos pela API.

### 6.1 Carregar repositórios

O método:

```python
_carregar_repos_github()
```

obtém o token de:

```python
config_github().token
```

Depois faz uma requisição autenticada à API:

```text
GET https://api.github.com/user/repos
```

Por isso os repositórios privados aparecem na lista quando a sessão está
autenticada.

### 6.2 Clone pela tela de boas-vindas

O fluxo atual usa:

```python
_WorkerClone
```

em:

```text
_APP_/Boas_Vindas/dialogo_novo_projeto.py
```

O picker obtém o token da sessão e passa o valor em memória ao worker.

O worker tenta criar uma credencial temporária para o Git, sem colocar o token
na URL do clone.

Esse fluxo é diferente do método antigo de `git_gerente.py`. A existência de
dois fluxos diferentes é a principal fonte de inconsistência do clone privado.

---

## 7. Pipeline atual completo

### 7.1 Boot sem projeto

```text
main.py
└── QApplication
    └── JanelaPicker(modo="boot")
```

O usuário pode:

```text
abrir projeto local
criar projeto
clonar repositório
entrar no GitHub indiretamente ao carregar repositórios
ou não fazer login
```

### 7.2 Abrir projeto local com Git

```text
usuário escolhe uma pasta
└── projeto é lançado em nova instância
    └── MainWindow
        └── PainelGitHub
            └── set_projeto(caminho)
```

Se a pasta já tem `.git`:

```text
set_projeto()
└── GitUIProjeto.abrir_projeto(caminho)
    └── mostra tela C
```

Mesmo que não exista conta GitHub, a tela C pode ser mostrada porque Git local
não depende de login remoto.

### 7.3 Abrir projeto local sem Git

```text
set_projeto()
└── GitUIConta.set_projeto(caminho)
    └── mostra tela B
```

Nesse caso, a tela B oferece ações relacionadas à publicação, mas o usuário
precisa estar autenticado para usar a API GitHub.

### 7.4 Login pelo painel Git antigo

```text
PainelGitHub
└── tela A
    └── GitUIEntrar
        └── GerenciadorAuth
            └── Device Flow
                └── config_github().registrar_sessao(...)
                    └── volta para tela B
```

### 7.5 Troca de conta pelo painel antigo

```text
tela B
└── menu Contas
    ├── conta salva 1
    ├── conta salva 2
    ├── Adicionar outra conta
    └── Sair da conta atual
```

Ao trocar, `config_github().ativar_conta(login)` muda o token e a conta ativa.

### 7.6 Clone pela tela B

```text
tela B
└── Baixar
    └── pede URL
        └── pede pasta
            └── GerenciadorGit.baixar_projeto(...)
```

Esse é o fluxo antigo e não deve continuar existindo como uma implementação
independente do clone usado na tela de boas-vindas.

### 7.7 Clone pela tela de boas-vindas

```text
JanelaPicker
└── carregar repositórios ou colar URL
    └── _executar_clone()
        └── _WorkerClone em QThread
            └── git clone
                └── abre o projeto em processo novo
```

Esse fluxo deve se tornar a referência única de clone, depois de sua
autenticação ser finalizada e validada no Windows.

---

## 8. Por que a arquitetura ficou redundante

A arquitetura original foi criada antes da tela de boas-vindas existir.

Na arquitetura antiga:

```text
Painel Git
├── A — login
├── B — conta e repositórios
└── C — projeto aberto
```

Depois foi criada a tela de boas-vindas para abrir e criar projetos antes de
entrar no editor. Ela passou a oferecer:

- campo de clone;
- carregar repositórios;
- autenticação indireta;
- escolha de projeto.

O painel Git antigo continuou existindo para não quebrar o editor. O resultado
foi:

```text
Tela de boas-vindas
└── clone e repositórios

Painel Git antigo
├── A — login
├── B — conta e clone novamente
└── C — projeto
```

A duplicação é de interface e de fluxo. A sessão em si é compartilhada por
`config_github()`, mas as ações de clone não são compartilhadas.

Isso explica o problema observado:

- a API consegue listar o repositório privado;
- o clone público funciona;
- o clone privado pode falhar;
- dependendo de onde o clone é iniciado, um método diferente é executado;
- um método usa credencial temporária e outro coloca token na URL.

---

## 9. Decisão arquitetural proposta

### 9.1 Login deve ser opcional

Ao abrir a tela de boas-vindas, a IDE não deve obrigar o usuário a entrar no
GitHub.

O usuário pode simplesmente:

```text
abrir projeto local
criar projeto
usar Git local
```

Sem token, o Git local continua funcionando.

### 9.2 Login deve funcionar em qualquer momento

O usuário deve poder iniciar o login:

1. na tela de boas-vindas;
2. no painel Git quando já estiver dentro de um projeto;
3. ao escolher `Adicionar outra conta`;
4. ao tentar uma operação GitHub que exige autenticação.

Todos esses caminhos devem chamar o mesmo componente de autenticação:

```python
GerenciadorAuth
```

Nenhuma tela deve criar um Device Flow próprio.

### 9.3 A sessão continua única

Depois do login, qualquer tela deve ler a mesma sessão:

```python
config_github()
```

Não criar:

- token específico da tela de boas-vindas;
- token específico da tela B;
- token específico da tela C;
- arquivos de sessão separados.

### 9.4 A conta ativa deve ser visível

Quando houver uma conta ativa, o usuário deve conseguir identificar isso:

```text
@henriq
```

Quando não houver conta:

```text
GitHub não conectado
[Entrar no GitHub]
```

O estado deve ser atualizado nas telas depois de:

- login concluído;
- troca de conta;
- logout;
- cancelamento do login.

---

## 10. Fluxo proposto para a tela de boas-vindas

### 10.1 Sem login

```text
JanelaPicker
└── usuário abre ou cria projeto
    └── nenhum login necessário
```

Se o usuário clicar em `Carregar repositórios` sem sessão:

```text
GitHub não conectado
[Entrar no GitHub]
```

O botão não deve falhar silenciosamente e não deve fingir que houve uma lista
vazia de repositórios.

### 10.2 Login na tela de boas-vindas

```text
JanelaPicker
└── Entrar no GitHub
    └── componente Device Flow
        └── config_github().registrar_sessao(...)
            └── tela atualiza @usuário
                └── usuário pode carregar repositórios
```

### 10.3 Trocar conta na tela de boas-vindas

Quando houver mais de uma conta:

```text
@conta-atual  [Contas ▾]
```

Menu:

```text
@conta-1
@conta-2
Adicionar outra conta
Sair da conta atual
```

Ao selecionar uma conta:

```python
config_github().ativar_conta(login)
```

Depois disso:

1. atualizar o nome da conta;
2. recarregar os repositórios;
3. usar o token da nova conta em operações futuras;
4. não reutilizar a lista da conta anterior.

### 10.4 Lista de repositórios

A tela de boas-vindas continua sendo o local para mostrar a lista geral de
repositórios da conta, porque o projeto ainda não foi aberto.

Cada repositório deve mostrar:

- nome;
- indicador público/privado;
- ação de clonar.

O usuário pode clicar no nome para abrir a página web, mas isso não deve ser
confundido com o clone.

---

## 11. Fluxo proposto para entrar depois de abrir um projeto

Este é o cenário que não pode ser perdido.

### 11.1 Projeto aberto sem conta

```text
usuário abre projeto local
└── Painel Git
    └── tela C
        └── GitHub não conectado
            └── [Entrar no GitHub]
```

Ao clicar:

```text
GitUIProjeto
└── solicita abertura do componente de autenticação
    └── GerenciadorAuth
        └── Device Flow
            └── config_github().registrar_sessao(...)
                └── atualiza a tela C
```

O projeto não deve ser fechado. O usuário não deve voltar obrigatoriamente
para a tela de boas-vindas apenas para fazer login.

### 11.2 Projeto aberto com conta

O cabeçalho ou a área GitHub da tela C deve mostrar:

```text
GITHUB   @henriq   [Contas ▾]
```

O menu deve permitir:

```text
Trocar conta
Adicionar outra conta
Sair da conta atual
```

### 11.3 Projeto sem remoto

Se o projeto local ainda não tiver `origin`:

```text
GitHub não vinculado
[Criar repositório no GitHub]
[Vincular repositório existente]
```

Se não houver sessão e o usuário clicar em uma dessas ações:

```text
Nenhuma sessão ativa
[Entrar no GitHub]
```

Depois que o login terminar, a ação original pode:

- continuar automaticamente, se o fluxo for seguro e claro; ou
- informar que o usuário deve clicar novamente.

A primeira versão deve preferir informar claramente o próximo passo, em vez
de executar uma ação remota inesperada.

### 11.4 Projeto com remoto

Se houver `origin`, a tela C mostra o estado do remoto e libera:

- commit local;
- push autenticado;
- pull autenticado;
- histórico;
- branches.

Git local deve continuar podendo fazer commit sem sessão. Push e pull podem
exigir autenticação dependendo do remoto.

---

## 12. O que fazer com A, B e C

### 12.1 A — manter como componente de autenticação

Arquivo:

```text
_PAINEL_ESQUERDO_/Git/a__git_ui_entrar.py
```

Proposta:

- manter o Device Flow;
- manter o painel visual do código;
- permitir que a tela seja aberta por outros contextos;
- evitar tratá-la como único ponto de login da aplicação;
- não duplicar sua lógica em `janela_picker.py` ou na tela C.

A pode continuar sendo uma página interna do `PainelGitHub` durante a
transição, mas a arquitetura final deve tratá-la como componente de login
reutilizável.

### 12.2 B — manter temporariamente e reduzir responsabilidades

Arquivo:

```text
_PAINEL_ESQUERDO_/Git/b__git_ui_conta.py
```

Não apagar imediatamente.

Motivos:

- o usuário pode abrir um projeto sem estar logado;
- depois pode querer entrar no GitHub;
- projetos sem `.git` atualmente passam pela tela B;
- a tela B ainda concentra publicação e conta;
- removê-la antes de migrar os fluxos quebraria caminhos existentes.

Primeira etapa:

- remover a duplicação do clone;
- fazer o fluxo de conta reutilizar o mesmo componente de autenticação;
- manter temporariamente publicação e ações compatíveis;
- adicionar migração gradual das ações para a tela C ou para um componente
  compartilhado.

Etapa posterior, somente após validação:

- transformar B em painel reutilizável de conta;
- ou reduzir B ao estado de projeto sem Git;
- ou remover B do `QStackedWidget` quando todos os seus contratos tiverem
  destino claro.

### 12.3 C — manter e adicionar acesso à conta

Arquivo:

```text
_PAINEL_ESQUERDO_/Git/c__git_ui_projeto/_projeto.py
```

Proposta:

- manter todas as operações do projeto;
- mostrar conta ativa ou estado não conectado;
- oferecer login quando não houver sessão;
- oferecer troca/adicionar conta quando houver sessão;
- oferecer criação e vínculo de remoto;
- bloquear ou explicar claramente operações que exigem sessão;
- atualizar o estado depois de login, troca e logout.

Não transformar C em uma lista geral de todos os repositórios da conta. A C
deve continuar focada no projeto aberto.

### 12.4 `git_ui.py` — orquestrar estados sem apagar o fluxo antigo cedo demais

Arquivo:

```text
_PAINEL_ESQUERDO_/Git/git_ui.py
```

Deve continuar controlando as telas durante a migração.

Depois da migração, deve controlar principalmente:

```text
autenticação
conta ativa
projeto atual
estado do remoto
```

O `QStackedWidget` pode continuar existindo mesmo que a tela B seja reduzida.
A remoção da tela B só deve acontecer em uma etapa posterior e validada.

---

## 13. Clone público e privado

### 13.1 Por que o público funciona sem autenticação

Um repositório público pode ser clonado sem token. Portanto, um clone público
bem-sucedido não comprova que a autenticação do Git está correta.

### 13.2 Por que o privado falha com `Repository not found`

A API pode listar o repositório privado porque recebeu um token HTTP válido.

O processo Git é separado:

```text
API GitHub
└── Authorization via header

git clone
└── credencial fornecida por helper, askpass ou URL
```

Se o segundo processo não receber a credencial correta, o GitHub pode responder
como se o repositório não existisse:

```text
remote: Repository not found.
fatal: repository ... not found
```

### 13.3 Problema atual de duplicidade

O worker da tela de boas-vindas tenta usar arquivo temporário de credencial.

O método antigo em `git_gerente.py` faz:

```python
url_com_token = url.replace("https://", f"https://{token}@")
```

Esses caminhos não devem continuar coexistindo.

### 13.4 Fluxo único proposto

Deve existir uma única operação de clone autenticado, usada por qualquer UI:

```text
UI
└── chama serviço de clone
    └── recebe URL, destino e sessão ativa
        └── cria credencial temporária em memória/disco temporário
            └── executa git clone com helper isolado
                └── remove credencial em sucesso
                └── remove credencial em erro
                └── remove credencial em timeout
```

Regras do comando:

1. Não colocar token na URL.
2. Não colocar token em logs.
3. Não colocar token em mensagens de erro.
4. Limpar helpers globais que possam fornecer credencial errada.
5. Usar apenas o helper temporário daquela operação.
6. Não gravar credencial permanente sem consentimento explícito.
7. Preservar a URL original do remoto em `.git/config`, sem token.
8. Remover pasta parcial do clone quando a operação falhar, se ela tiver sido
   criada exclusivamente por aquela tentativa.
9. Não apagar uma pasta preexistente sem confirmação.
10. Confirmar o fluxo com repositório privado no Windows.

### 13.5 Push e pull

O mesmo princípio vale para:

- push;
- pull;
- fetch;
- atualização de remoto.

Não se deve confiar em `GIT_ASKPASS="echo"` como se isso, sozinho, fornecesse
o token ao Git. O mecanismo de credencial precisa entregar de fato usuário e
token ao processo Git.

---

## 14. Problemas de segurança que devem ser corrigidos durante a migração

### 14.1 Resposta OAuth no log

Em `git_autentica.py`, a resposta completa do GitHub é registrada. Essa
resposta pode conter `access_token`.

Não registrar a resposta completa. O log deve conter apenas dados seguros,
como:

```text
autorização pendente
token recebido
login obtido
id do usuário
```

Nunca registrar o valor do token.

### 14.2 Token na URL

Remover o padrão de inserir token em:

```text
https://TOKEN@github.com/...
```

Isso pode expor o token em:

- histórico de comandos;
- mensagens de erro;
- arquivos de configuração;
- ferramentas de diagnóstico;
- logs de processo.

### 14.3 Token em `remote.origin.url`

O remoto gravado no `.git/config` deve ser uma URL normal:

```text
https://github.com/usuario/repositorio.git
```

Nunca deve conter o token.

---

## 15. Plano de implementação proposto

Esta é a ordem sugerida. Não é autorização automática para executar as etapas.

### Etapa 1 — consolidar o contrato da sessão

Arquivos:

```text
git_config.py
git_autentica.py
```

Objetivos:

- confirmar que toda UI lê a mesma sessão;
- impedir log de token;
- manter Device Flow único;
- atualizar a UI após login, troca e logout.

### Etapa 2 — criar um ponto reutilizável de autenticação

Arquivos possíveis:

```text
a__git_ui_entrar.py
git_ui.py
```

Objetivos:

- permitir abrir o Device Flow pela tela de boas-vindas;
- permitir abrir o Device Flow com projeto aberto;
- permitir adicionar conta;
- não duplicar lógica de polling.

Se for necessário criar um novo componente, ele deve ficar dentro do módulo
Git e ter responsabilidade única. A criação de novo arquivo deve ser
confirmada pela análise da outra IA antes da implementação.

### Etapa 3 — colocar estado de conta na tela de boas-vindas

Arquivo:

```text
_APP_/Boas_Vindas/janela_picker.py
```

Objetivos:

- mostrar conta ativa;
- oferecer login quando não houver token;
- oferecer trocar/adicionar conta;
- recarregar repositórios quando a conta mudar;
- manter login opcional.

### Etapa 4 — unificar clone

Arquivos:

```text
_APP_/Boas_Vindas/dialogo_novo_projeto.py
_APP_/Boas_Vindas/janela_picker.py
_PAINEL_ESQUERDO_/Git/git_gerente.py
_PAINEL_ESQUERDO_/Git/b__git_ui_conta.py
```

Objetivos:

- um único serviço de clone;
- clone público e privado pelo mesmo caminho;
- nenhum token na URL;
- helper temporário isolado;
- mensagens seguras;
- preservar `.git`.

### Etapa 5 — oferecer login dentro do projeto

Arquivos:

```text
_PAINEL_ESQUERDO_/Git/c__git_ui_projeto/_projeto.py
_PAINEL_ESQUERDO_/Git/git_ui.py
```

Objetivos:

- mostrar “Entrar no GitHub” quando não houver sessão;
- mostrar conta ativa quando houver;
- permitir trocar/adicionar conta;
- continuar no projeto depois do login;
- permitir criar/vincular remoto depois da autenticação.

### Etapa 6 — reduzir a duplicação da B

Arquivo:

```text
_PAINEL_ESQUERDO_/Git/b__git_ui_conta.py
```

Somente depois das etapas anteriores:

- retirar o clone duplicado;
- retirar login duplicado;
- manter o que ainda for necessário para projeto sem Git;
- decidir se B será painel de conta, painel de publicação ou componente
  temporário de transição.

### Etapa 7 — revisar o orquestrador

Arquivo:

```text
_PAINEL_ESQUERDO_/Git/git_ui.py
```

Somente depois de os fluxos estarem cobertos:

- rever estados do `QStackedWidget`;
- eliminar transições sem uso;
- manter compatibilidade com `MainWindow`;
- não quebrar sinais de projeto, commit e push.

---

## 16. O que não deve ser feito

1. Não apagar `b__git_ui_conta.py` antes de criar o login posterior ao projeto.
2. Não obrigar login no boot.
3. Não mandar o usuário de volta à tela de boas-vindas apenas para autenticar.
4. Não criar um segundo Device Flow.
5. Não duplicar tokens em memória sem necessidade.
6. Não criar um segundo arquivo de configuração de contas.
7. Não manter dois métodos de clone autenticado.
8. Não colocar token na URL.
9. Não registrar resposta OAuth completa.
10. Não mudar a função da tela C para virar navegador de repositórios.
11. Não misturar Git local com autenticação GitHub.
12. Não alterar o fluxo de venv, Python, threads ou criação de projetos sem
    instrução específica.
13. Não fazer uma grande remoção/refatoração antes de validar os fluxos
    existentes.

---

## 17. Matriz de comportamento esperada

| Situação | Deve funcionar sem login? | Ação esperada |
|---|---:|---|
| Abrir projeto local | Sim | Abrir o projeto |
| Criar projeto local | Sim | Criar e abrir |
| `git init` local | Sim | Inicializar Git local |
| Fazer commit local | Sim | Criar commit |
| Ver status local | Sim | Mostrar alterações |
| Carregar repositórios GitHub | Não | Pedir login |
| Clonar repositório público | Geralmente sim | Clonar |
| Clonar repositório privado | Não | Pedir login e autenticar Git |
| Criar repositório remoto | Não | Pedir login |
| Publicar projeto | Não | Pedir login |
| Push HTTPS | Não | Usar sessão ativa |
| Pull HTTPS | Não | Usar sessão ativa |
| Trocar conta | Não | Usar conta salva ou autenticar |
| Abrir tela Git do projeto | Sim | Mostrar Git local e estado GitHub |
| Entrar depois de abrir projeto | Sim, como ação | Abrir Device Flow sem fechar projeto |

---

## 18. Critérios de aceite

### Login e contas

- [ ] A IDE abre sem exigir login.
- [ ] Usuário sem conta consegue abrir e criar projetos.
- [ ] Login pela tela de boas-vindas funciona.
- [ ] Login com projeto aberto funciona.
- [ ] O projeto aberto não é fechado durante o login.
- [ ] A conta ativa fica visível.
- [ ] Trocar conta atualiza a sessão usada nas operações seguintes.
- [ ] Adicionar conta não apaga as contas anteriores.
- [ ] Logout remove a sessão ativa sem apagar arquivos locais.

### Repositórios

- [ ] Repositórios públicos aparecem.
- [ ] Repositórios privados aparecem quando a conta tem acesso.
- [ ] A lista é recarregada ao trocar de conta.
- [ ] O usuário consegue clonar da tela de boas-vindas.
- [ ] O botão de clone da tela B não executa um caminho incompatível.

### Clone privado

- [ ] Clone privado termina com sucesso no Windows.
- [ ] A pasta `.git` é criada.
- [ ] O remoto original é preservado sem token na URL.
- [ ] O projeto abre em nova instância.
- [ ] O painel Git reconhece o remoto.
- [ ] O token não aparece na interface.
- [ ] O token não aparece no log.
- [ ] O token não aparece nos argumentos do processo.
- [ ] O arquivo temporário de credencial é removido.
- [ ] Uma tentativa falha sem apagar uma pasta preexistente sem confirmação.

### Projeto aberto

- [ ] Projeto sem remoto mostra opção clara de login/vínculo.
- [ ] Projeto com remoto mostra a conta ativa.
- [ ] Push e pull usam a sessão atual.
- [ ] Troca de conta atualiza o estado visual.
- [ ] Git local continua funcionando sem conta.

---

## 19. Testes manuais obrigatórios no Windows

1. Abrir a IDE sem login.
2. Abrir um projeto local sem `.git`.
3. Criar commit local sem login.
4. Abrir um projeto local com `.git`.
5. Entrar no GitHub com o projeto já aberto.
6. Trocar para uma segunda conta.
7. Adicionar uma nova conta.
8. Fazer logout com projeto aberto.
9. Carregar repositórios na tela de boas-vindas.
10. Clonar repositório público.
11. Clonar repositório privado acessível à conta.
12. Confirmar `.git` e `origin`.
13. Alterar arquivo, fazer commit e push.
14. Fazer pull de uma alteração remota.
15. Fechar a IDE durante Device Flow.
16. Fechar a IDE durante clone.
17. Confirmar remoção da credencial temporária.
18. Confirmar que nenhum token apareceu em log, URL ou mensagem.

---

## 20. Conclusão

A tela B não deve ser apagada agora.

O motivo é simples: o usuário pode abrir um projeto sem login e decidir entrar
no GitHub depois. Enquanto esse fluxo não estiver disponível diretamente na
tela C ou em um componente compartilhado, a remoção da B quebraria uma
capacidade real do aplicativo.

A direção segura é:

```text
Tela de boas-vindas
└── login opcional, contas, repositórios e clone

Painel Git com projeto aberto
└── login posterior, conta ativa, vínculo e operações do projeto

Tela A
└── componente único do Device Flow

Tela B
└── manter durante a migração; reduzir depois

Tela C
└── manter para o projeto aberto e adicionar acesso à conta

Camada Git compartilhada
└── uma sessão, uma API e um fluxo único de clone autenticado
```

Nenhuma implementação deve remover telas ou alterar contratos antes que os
critérios de aceite desta documentação sejam atendidos.