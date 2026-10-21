# Tradutor de Erros — Documentação Completa
## IDE hein · Módulo `_TRADUTION_/`

---

## 1. História e Motivação

A IDE hein é um editor de código em Python para o público brasileiro, construído com PySide6.
O problema central era simples: **todos os erros do Python, do pip e do PowerShell chegavam em inglês** para o usuário.

Mensagens como:

```
NameError: name 'x' is not defined
ModuleNotFoundError: No module named 'numpy'
'python' is not recognized as an internal or external command
```

São incompreensíveis para iniciantes brasileiros. O objetivo era **traduzir automaticamente para português** essas mensagens, sem depender de IA, sem custo, sem conexão com internet, e de forma rápida o suficiente para não travar o terminal.

---

## 2. O Que Foi Criado

### Estrutura do módulo

```
_TRADUTION_/
├── __init__.py
├── tradutor_erros.py          ← ponto de entrada público (não muda nunca)
├── _motor.py                  ← lógica das camadas + cache LRU
├── _testes.py                 ← 76 testes de regressão automatizados
└── _dados/
    ├── camada0_pre.py         ← pré-processamento e proteção
    ├── camada1_frases.py      ← ~875 frases exatas
    ├── camada2_regex.py       ← 70 padrões regex com capture groups
    ├── camada3_palavras.py    ← ~500 palavras (dicionário fallback)
    └── camada4_pos.py         ← pós-processamento e restauração
```

### Integração nos terminais e editor

```
_TERMINAIS_/terminal_run.py          ← terminal de execução (Run)
_TERMINAIS_/terminal_powershell.py   ← terminal interativo (PowerShell)
_EDITOR_/Outline/painel_outline.py   ← painel de estrutura do código
```

### API pública (uso simples)

```python
from _TRADUTION_.tradutor_erros import traduzir

texto_em_portugues = traduzir("NameError: name 'x' is not defined")
# → "Erro de nome: nome 'x' não está definido"
```

O arquivo `tradutor_erros.py` é uma fachada imutável — apenas re-exporta a função `traduzir` do `_motor.py`. Todos os terminais importam daqui.

---

## 3. Como Funciona — As 5 Camadas

O tradutor aplica **cinco camadas em sequência**. A ordem é imutável — alterá-la quebra a tradução.

```
Texto em inglês
      │
      ▼
┌─────────────────────────────────────────┐
│  CAMADA 0a — Normaliza underscores      │  ← sem proteger aspas ainda
│  ex: no_such_file → no such file        │
└─────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────┐
│  CAMADA 2 — Regex com capture groups    │  ← precisa ver as aspas originais
│  Preserva nomes de variáveis/módulos    │
│  ~40 padrões                            │
└─────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────┐
│  CAMADA 1 — Frases exatas               │  ← precisa ver as aspas originais
│  ~692 frases completas, case-insensitive│
│  ex: "no such file or directory"        │
└─────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────┐
│  CAMADA 0b — Protege conteúdo entre     │  ← bloqueia Camada 3 de traduzir
│  aspas no cofre temporário              │  ← 'config.json' fica intocável
│  + protege caminhos, versões, pacotes   │
└─────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────┐
│  CAMADA 3 — Dicionário palavra-a-palavra│  ← aspas já protegidas
│  ~500 palavras com \b word boundary     │
│  Fallback para o que sobrar em inglês   │
└─────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────┐
│  CAMADA 4 — Pós-processamento           │  ← restaura, limpa, capitaliza
│  Restaura conteúdo do cofre             │
│  Remove redundâncias (~50 padrões)      │
│  Corrige capitalização da primeira letra│
└─────────────────────────────────────────┘
      │
      ▼
Texto em português
```

### Por que a Camada 2 roda ANTES da Camada 1?

Esta foi a descoberta mais importante do desenvolvimento.

Inicialmente a Camada 1 rodava primeiro. O problema: a frase `"is not defined"` era substituída por `"não está definido"` antes do regex ter chance de capturar o nome da variável.

**Exemplo do problema (ordem errada):**
```
Entrada:  NameError: name 'x' is not defined
Camada 1: NameError: name 'x' não está definido   ← quebrou o regex!
Camada 2: regex não casa mais (esperava "is not defined")
Resultado: Erro de nome: name 'x' não está definido  ← "name" em inglês!
```

**Com a ordem correta (Camada 2 primeiro):**
```
Entrada:  NameError: name 'x' is not defined
Camada 2: Erro de nome: nome 'x' não está definido  ← perfeito!
Camada 1: (nada mais a substituir)
Camada 3: (nada mais a substituir)
```

### Por que a Camada 0b roda DEPOIS da Camada 1?

A Camada 0b protege o conteúdo entre aspas para que a Camada 3 não o traduza. Ela precisa rodar depois das Camadas 2 e 1 porque elas ainda precisam enxergar as aspas originais para funcionar corretamente.

Se a 0b rodasse antes, o regex da Camada 2 não conseguiria capturar os grupos `'numpy'`, `'x'`, etc.

---

## 4. Detalhamento das Camadas

### Camada 0a — Normalização de Underscores

Roda antes de tudo, sem proteger aspas ainda.

```python
def normalizar_underscores(texto: str) -> str:
    # Converte underscores ISOLADOS em espaços (sem letra/dígito/_ em nenhum lado)
    # Preserva: __init__, win_amd64, _private, no_such_file (entre letras)
    return re.sub(r'(?<!\w)_(?!\w)', ' ', texto)
```

Variantes com underscore de erros do OS (ex: `no_such_file`) têm entradas
explícitas no C1 (`"no_such_file_or_directory"` etc.) para cobrir esses casos.

### Camada 0b — Proteção do Cofre (7 tipos de proteção, em ordem)

A Camada 0 usa um cofre (`dict`) com marcadores únicos (`\x00ASPAS{i}\x00`) para proteger trechos que não devem ser traduzidos. A Camada 4 os restaura depois.

**Ordem de proteção (imutável):**

| Prioridade | O que protege | Exemplo |
|-----------|---------------|---------|
| 1 | Aspas simples e duplas | `'config.json'`, `"requests"` |
| 2 | Caminhos Windows fora de aspas | `C:\Users\foo\bar.py` |
| 3 | Caminhos Unix fora de aspas | `/usr/local/bin/python` |
| 4 | Linhas de código indentadas no traceback | `    import numpy` (4 espaços) |
| 5 | Nomes de classe de erro | `TypeError`, `NameError`, `ValueError` |
| 6 | Pacotes pip com versão | `requests-2.28.0` |
| 7 | Versões numéricas soltas | `3.11.2`, `v2.0.1` |

A ordem importa: aspas primeiro garante que caminhos dentro de aspas não sejam reprocessados. Linhas de código indentadas (prioridade 4) resolvem o problema histórico de `import numpy` virar `importar numpy` no traceback.

### Camada 2 — Regex com Capture Groups (70 padrões)

Esses padrões capturam **o nome da variável, módulo ou arquivo** e os preservam na tradução:

| Padrão | Exemplo entrada | Saída |
|--------|----------------|-------|
| `NameError: name 'X' is not defined` | `name 'contador' is not defined` | `nome 'contador' não está definido` |
| `AttributeError: 'X' object has no attribute 'Y'` | `'NoneType' object has no attribute 'split'` | `objeto 'NoneType' não tem atributo 'split'` |
| `ModuleNotFoundError: No module named 'X'` | `No module named 'numpy'` | `módulo 'numpy' não encontrado` |
| `ImportError: cannot import name 'X' from 'Y'` | `cannot import name 'DataFrame' from 'pandas'` | `não foi possível importar 'DataFrame' de 'pandas'` |
| `TypeError: 'X' object is not subscriptable` | `'int' object is not subscriptable` | `objeto 'int' não é indexável` |
| `FileNotFoundError: [Errno 2] No such file... 'X'` | `No such file or directory: 'config.json'` | `arquivo ou diretório inexistente: 'config.json'` |
| `File "X", line N, in Y` | `File "main.py", line 42, in <module>` | `Arquivo "main.py", linha 42, em <módulo>` |
| `Process finished with exit code N` | `exit code 1` | `Processo finalizado com código de saída 1` |
| `'X' is not recognized as an internal...` | `'python' is not recognized...` | `'python' não é reconhecido como comando interno ou externo` |
| `Downloading X.whl (N MB)` | `Downloading numpy-1.26.0-cp311.whl (15.3 MB)` | `Baixando numpy-1.26.0-cp311.whl (15.3 MB)` |
| `Collecting X>=N` | `Collecting numpy>=1.21` | `Coletando numpy>=1.21` |
| `operands could not be broadcast together with shapes X Y` | `shapes (3,) (4,)` | `operandos não podem ser combinados com os formatos (3,) e (4,)` |
| `cannot reshape array of size N into shape X` | `size 6 into shape (2,4)` | `não é possível reformatar array de tamanho 6 para o formato (2,4)` |
| `index N is out of bounds for axis M with size K` | `index 5 is out of bounds for axis 0 with size 4` | `índice 5 fora dos limites para o eixo 0 de tamanho 4` |
| `shapes X and Y not aligned` | `shapes (3,3) and (4,4) not aligned` | `formatos (3,3) e (4,4) são incompatíveis` |
| `collected N items` | `collected 12 items` | `12 teste(s) coletado(s)` |
| `N passed[, M failed][, K errors] in Xs` | `3 failed, 2 passed in 1.05s` | `3 reprovado(s), 2 aprovado(s)` |
| `Cannot install X and Y because conflicting dependencies` | `Cannot install flask and requests...` | `Não é possível instalar flask e requests...` |
| `X Y requires Z, but you have W which is incompatible` | `flask 2.0 requires click>=8.0...` | `flask 2.0 requer click>=8.0...` |

### Camada 1 — Frases Exatas (~875 frases)

Organizada por categoria, do mais específico ao mais genérico dentro de cada bloco:

- **Python — Traceback / estrutura**: `"Traceback (most recent call last)"`, `"during handling of the above exception"`
- **SyntaxError completo**: todos os casos do parser do CPython, incluindo `"was never closed"`, `"expected ':'"`
- **Erros de tipo, valor, índice**: `"division by zero"`, `"list index out of range"`, `"unhashable type"`
- **Import e módulos**: `"cannot import name"`, `"circular import"`, `"partially initialized module"`
- **Async/await e generators**: `"coroutine was never awaited"`, `"async generator"`
- **pip — instalação**: `"successfully installed"`, `"requirement already satisfied"`, `"no matching distribution found"`, `"wheels"`, `"virtualenv"`
- **pip help — saída de uso**: linhas fixas do `pip --help` — descrições de comandos (`install`, `download`, `list`, etc.) e opções gerais, incluindo **fragmentos de linha** para cada opção do `General Options` (o pip quebra descrições longas em múltiplas linhas; cada linha chega separada ao `traduzir()`, então cada fragmento tem entrada própria)
- **pip conflitos de dependência**: bloco completo do resolvedor — `"pip's dependency resolver..."`, `"The conflict is caused by:"`, `"To fix this you could try to:"` e continuações
- **Rede — SSL, DNS, HTTP**: `"certificate verify failed"`, `"name or service not known"`, status HTTP 400→504
- **Windows/PowerShell**: políticas de execução, handles, paths longos
- **Git**: conflitos, autenticação, branches, push/pull
- **Docker**: daemon, containers, imagens, volumes, redes
- **Django/Flask**: migrations, models, validação de formulário
- **SQLite**: locks, constraints, integridade referencial
- **pyflakes/lint**: `"imported but unused"`, `"redefinition of unused"`
- **numpy/scipy**: `"setting an array element with a sequence"`, `"could not broadcast input array"`, `"matmul: input operand"`, `"axis out of range"`, `"array is read-only"`, `"data type not understood"`
- **pandas**: `"the truth value of a Series is ambiguous"`, `"cannot reindex from a duplicate axis"`, `"incompatible indexer with series"`, `"no columns to parse from file"`
- **requests/urllib3**: `"too many redirects"`, `"missing dependencies for SOCKS support"`, `"invalid proxy url"`
- **SQLAlchemy**: `"this session's transaction has been rolled back"`, `"can't reconnect until invalid transaction is rolled back"`, `"instance is not bound to a session"`, `"ambiguous column name"`
- **pytest**: `"short test summary info"`, `"warnings summary"`, `"rootdir:"`, `"xfailed"`, `"xpassed"`, `"setup failed"`, `"teardown failed"`, `"no tests ran"`

### Camada 3 — Dicionário Palavra-a-Palavra (~500 palavras)

Fallback para tudo que as camadas anteriores não cobriram. Palavras-chave Python que poderiam causar tradução indevida de código do usuário foram **removidas** desta camada (cobertas pela Camada 1 no contexto correto):

**Removidas da Camada 3 (causavam tradução de código do usuário):**
```python
# Estas entradas foram removidas porque traduziam código Python do traceback:
("import",  "importar"),
("from",    "de"),
("return",  "retorno"),
("with",    "com"),
("or",      "ou"),
("and",     "e"),
("not",     "não"),
("class",   "classe"),
```

**Categorias mantidas:**
- Classes de erro Python: `AttributeError`, `KeyError`, `TypeError`, `MemoryError`, etc.
- Sistema: `file`, `directory`, `path`, `permission`, `process`, `memory`, `disk`
- Rede: `connection`, `server`, `client`, `port`, `protocol`, `socket`
- Módulos Python: `module`, `function`, `argument`, `iterator`, `generator`
- Git: `branch`, `commit`, `merge`, `conflict`, `repository`
- Docker: `container`, `image`, `volume`, `layer`
- Banco de dados: `database`, `query`, `transaction`, `schema`, `migration`

### Camada 4 — Pós-processamento

Roda depois de todas as outras camadas. Três responsabilidades:

**1. Restaurar o cofre**
```python
def restaurar(texto: str, cofre: dict) -> str:
    for chave, valor in cofre.items():
        texto = texto.replace(chave, valor)
    return texto
```

**2. Remover redundâncias (~50 padrões)**

A tradução em cascata pode gerar frases redundantes. Exemplos corrigidos:
```
"Erro de divisão por zero: divisão por zero"  →  "Erro de divisão por zero"
"Módulo não encontrado: módulo 'x' não encontrado"  →  "Módulo não encontrado: 'x'"
"Arquivo não encontrado: arquivo inexistente"  →  "Arquivo não encontrado"
```

Também inclui `limpar_artefatos()` que remove espaços duplos gerados pela tradução.

**3. Corrigir capitalização**
```python
def corrigir_capitalizacao(texto: str) -> str:
    # Capitaliza 1ª letra da linha quando está em minúsculo.
    # ⚠️ Pula linhas que começam com espaço ou tab — são código do
    # traceback restaurado pelo Cofre e não devem ser capitalizadas.
```

> **Bug histórico resolvido:** antes da correção, linhas de código do traceback
> como `    import numpy` eram capitalizadas para `    Import numpy` após a
> restauração do Cofre. O Cofre protegia a linha, a restaurava como texto puro,
> e então a capitalização agia sobre ela. Corrigido em 2026-08-05.

---

## 5. Resultados — Exemplos Reais

| Entrada (inglês) | Saída (português) |
|------------------|-------------------|
| `NameError: name 'x' is not defined` | `Erro de nome: nome 'x' não está definido` |
| `ModuleNotFoundError: No module named 'numpy'` | `Módulo não encontrado: módulo 'numpy' não encontrado` |
| `AttributeError: 'NoneType' object has no attribute 'split'` | `Erro de atributo: objeto 'NoneType' não tem atributo 'split'` |
| `TypeError: unsupported operand type(s) for +: 'int' and 'str'` | `Erro de tipo: tipos de operando não suportados para +: 'int' e 'str'` |
| `IndentationError: unexpected indent` | `Erro de indentação: indentação inesperada` |
| `ZeroDivisionError: division by zero` | `Divisão por zero: divisão por zero` |
| `FileNotFoundError: [Errno 2] No such file or directory: 'config.json'` | `Arquivo não encontrado: arquivo ou diretório inexistente: 'config.json'` |
| `PermissionError: [WinError 5] Access is denied: 'C:/Windows'` | `Erro de permissão: acesso negado: 'C:/Windows'` |
| `'python' is not recognized as an internal or external command` | `'python' não é reconhecido como comando interno ou externo` |
| `Process finished with exit code 1` | `Processo finalizado com código de saída 1` |
| `Successfully installed requests-2.28.0` | `Instalado com sucesso: requests-2.28.0` |
| `imported but unused` | `importado mas não utilizado` |
| `connection refused` | `conexão recusada` |
| `permission denied` | `permissão negada` |
| `    import numpy` (linha indentada do traceback) | `    import numpy` ← **protegida, não traduzida** |

---

## 6. Onde Foi Integrado

### `terminal_run.py` — Terminal de Execução

```python
from _TRADUTION_.tradutor_erros import traduzir

def _ler_erro(self):
    err = self.process.readAllStandardError().data().decode("utf-8", errors="replace")
    err = traduzir(err)          # ← traduz antes de imprimir
    cor_erro = tema_global().cor("terminal_run.texto_erro", "#e06c75")
    self._imprimir_com_links(f"\n[ERRO] {err}\n", cor_erro)
```

### `terminal_powershell.py` — Terminal Interativo

```python
from _TRADUTION_.tradutor_erros import traduzir

def _ler_erro(self):
    raw  = self.process.readAllStandardError().data()
    text = raw.decode("utf-8", errors="replace")
    text = traduzir(text)        # ← traduz saída de erro
    self._inserir_ansi(text)
    self._mark_input_start()
```

> ⚠️ **Nota:** O `traduzir()` é aplicado **somente no `_ler_erro()`** do PowerShell, não no `_ler_saida()`. Aplicar no `_ler_saida()` causaria tradução do que o usuário digita (ex: `import requests` → `importar requisições`), o que é incorreto.

### `painel_outline.py` — Painel de Estrutura do Código

```python
from _TRADUTION_.tradutor_erros import traduzir

# No handler de SyntaxError:
self._label_status.setText(f"⚠ linha {e.lineno}: {traduzir(e.msg)}")
```

O Outline exibe mensagens de `SyntaxError` do parser do Python ao analisar o arquivo aberto. Essas mensagens chegam em inglês (`e.msg`) e agora são traduzidas antes de exibir.

### O que NÃO foi integrado (e por quê)

| Local | Motivo |
|-------|--------|
| **`_ler_saida()` do PowerShell** | Traduz o que o usuário digita — comportamento incorreto |
| **Editor (`_lint_rapido`)** | Só sublinha linhas visualmente, não exibe texto de erro |
| **Autocomplete** | Sugestões vêm do código do usuário — não há inglês fixo |

---

## 7. Prós e Contras

### ✅ Prós

| Vantagem | Detalhe |
|----------|---------|
| **Zero dependências externas** | Sem IA, sem API, sem internet. Funciona offline completamente. |
| **Velocidade** | Compilado na inicialização do módulo; cada chamada é microsegundos |
| **Preserva nomes de variáveis** | `name 'contador' is not defined` → preserva `'contador'` |
| **Preserva caminhos de arquivo** | `No such file: 'config.json'` → preserva `'config.json'` |
| **Preserva código do usuário no traceback** | Linhas indentadas com 4 espaços são protegidas inteiras pela Camada 0b |
| **Cache LRU** | Mesma mensagem repetida (ex: loop falhando 500×) custa zero após a 1ª vez |
| **Cobertura ampla** | ~875 frases + 70 regex + ~500 palavras = cobertura excelente |
| **Case-insensitive** | Funciona com `ERROR`, `Error`, `error` |
| **Extensível** | Basta adicionar uma linha no arquivo da camada correspondente |
| **Sem efeito colateral de UI** | Uma função pura: entrada string → saída string |

### ❌ Contras / Limitações

| Limitação | Exemplo | Detalhe |
|-----------|---------|---------|
| **Sem contexto semântico** | `run` → `executar` mesmo quando é nome de variável fora de aspas | Não sabe diferenciar `run` (verbo) de `run` (nome de variável sem aspas) |
| **Traduções compostas estranhas** | `"Divisão por zero: divisão por zero"` | Quando Camada 3 traduz o que a Camada 2 já tinha traduzido — a Camada 4 tenta mitigar com ~50 padrões de redundância |
| **Não cobre mensagens novas** | Erros de pacotes obscuros em inglês | O dicionário é finito; mensagens muito específicas de bibliotecas ficam em inglês |
| **Não localiza números** | `"42"` ainda é `"42"` (esperado) | Números de linha, versões, códigos de erro ficam intactos — isso é correto |

---

## 8. O Que Pode Melhorar

### 🔧 Melhorias técnicas

1. **Modo verboso / silencioso**
   ```python
   traduzir(texto, nivel="basico")   # só erros críticos
   traduzir(texto, nivel="completo") # tudo
   ```

2. **Arquivo de dicionário externo** `.json` ou `.toml`
   Permitir que o usuário adicione suas próprias traduções sem editar o código.

### 🌟 Novas funcionalidades

3. **Sugestão de correção**
   ```
   NameError: nome 'numpay' não está definido
   → Você quis dizer: import numpy?
   ```

4. **Detecção de erro recorrente**
   Contar quantas vezes o mesmo tipo de erro ocorre e oferecer dica:
   ```
   [3ª vez] IndentationError: indentação inesperada
   → Dica: Verifique se está misturando tabs e espaços
   ```

5. **Tradução de mensagens de linter (pyflakes)**
   Se o lint futuramente exibir mensagens em tooltip, o tradutor já estaria pronto para integração.

---

## 9. Arquitetura do Sistema

```
_TRADUTION_/
├── tradutor_erros.py          ← fachada pública imutável
│   └── re-exporta traduzir() de _motor.py
│
└── _motor.py                  ← orquestra as 5 camadas
    │
    ├── _dados/camada0_pre.py
    │   ├── normalizar_underscores()   ← Camada 0a
    │   └── proteger()                ← Camada 0b — retorna (texto, cofre)
    │
    ├── _dados/camada2_regex.py
    │   └── PADROES: list[tuple[Pattern, str]]   ← ~40 padrões compilados
    │
    ├── _dados/camada1_frases.py
    │   └── FRASES: list[tuple[str, str]]         ← ~692 frases
    │       └── compiladas em _motor.py no import
    │
    ├── _dados/camada3_palavras.py
    │   └── PALAVRAS: list[tuple[str, str]]       ← ~500 palavras
    │       └── compiladas em _motor.py no import
    │
    └── _dados/camada4_pos.py
        ├── restaurar(texto, cofre)
        ├── remover_redundancias(texto)    ← ~50 padrões
        └── corrigir_capitalizacao(texto)

    traduzir(texto: Any) -> str          ← ponto de entrada público
        1. str(texto)
        2. _traduzir_str(texto)          ← lru_cache(maxsize=512)
             2a. Camada 0a — normalizar_underscores()
             2b. Camada 2  — PADROES (70 regex com capture groups)
             2c. Camada 1  — FRASES_COMPILADAS (~875 frases exatas)
             2d. Camada 0b — proteger() → guarda cofre
             2e. Camada 3  — DICIONARIO_COMPILADO (~500 palavras)
             2f. Camada 4  — restaurar() + remover_redundancias()
                           + corrigir_capitalizacao() + limpar_artefatos()
        3. return texto

_TERMINAIS_/
├── terminal_run.py
│   └── _ler_erro() → err = traduzir(err) → _imprimir_com_links()
└── terminal_powershell.py
    └── _ler_erro() → text = traduzir(text) → _inserir_ansi()

_EDITOR_/Outline/
└── painel_outline.py
    └── SyntaxError handler → traduzir(e.msg) → _label_status.setText()
```

---

## 10. Decisões de Design

| Decisão | Alternativa descartada | Motivo da escolha |
|---------|----------------------|-------------------|
| **Módulo separado `_TRADUTION_/`** | Arquivo único `tradutor_erros.py` | Separa dados de lógica; cada camada tem seu arquivo próprio; fácil de expandir |
| **5 camadas sequenciais** | Dicionário único flat | Regex preservam variáveis; frases longas têm precedência; proteção do cofre é separada |
| **Camada 0b roda DEPOIS de Camada 1** | Proteger tudo antes de qualquer tradução | Camadas 1 e 2 precisam ver as aspas originais para funcionar |
| **Camada 2 roda antes da Camada 1** | Camada 1 primeiro (original) | Camada 1 quebrava os padrões de regex ao substituir frases-alvo antes |
| **Linhas indentadas protegidas na Camada 0b** | Não proteger | Resolve `import numpy` → `importar numpy` no traceback |
| **Palavras-chave Python removidas da Camada 3** | Manter `import`, `from`, `class`, etc. | Causavam tradução do código do usuário no traceback |
| **`traduzir()` só no `_ler_erro()` do PowerShell** | Aplicar em `_ler_saida()` também | `_ler_saida()` exibe o que o usuário digitou — não deve ser traduzido |
| **Sem IA** | GPT/Claude/Gemini via API | Zero custo, zero latência, funciona offline, sem dependência externa |
| **Compilar regex no import** | Compilar a cada chamada | Performance: compila uma vez, roda milhares de vezes |
| **`lru_cache(maxsize=512)` no núcleo** | Sem cache | Terminal repete a mesma mensagem em loops — cache zera o custo |
| **`list[tuple]` em vez de `dict`** | `dict` puro | A ordem dos padrões importa (frases longas antes de curtas) |
| **`re.IGNORECASE` em tudo** | Case-sensitive | Erros chegam em vários formatos: `ERROR`, `Error`, `error` |
| **Fragmentos por linha no C1 (pip --help)** | Frase completa única | pip quebra descrições em múltiplas linhas; cada linha chega separada ao `traduzir()` |
| **"have" no C3 com `\b`, não no C1** | "have" no C1 sem word boundary | Sem `\b`, batia dentro de "c**have**" e produzia "ctem" |
| **"cache" como empréstimo (C3 linha 689)** | "cache" → "armazenar em cache" | Locução verbal usada como substantivo gerava "o armazenar em cache do pip" |

---

## 11. Versão e Estatísticas

| Item | Quantidade |
|------|-----------|
| Arquivos do módulo | 7 (`tradutor_erros.py`, `_motor.py`, 4 camadas em `_dados/`, `_testes.py`) |
| Frases exatas (Camada 1) | ~875 |
| Padrões regex com grupos (Camada 2) | 70 |
| Palavras no dicionário (Camada 3) | ~500 |
| Padrões de redundância (Camada 4) | ~50 |
| Tipos de proteção (Camada 0b) | 7 |
| Testes de regressão automatizados | 76 |
| Cache LRU | 512 entradas |
| Categorias cobertas | 19+ (Python, pip, pip help General Options, pip conflitos, rede, HTTP, Windows, Git, Docker, DB, async, Django, SQLite, numpy/scipy, pandas, requests, SQLAlchemy, pytest...) |
| Integrações ativas | 3 (`terminal_run`, `terminal_powershell`, `painel_outline`) |
| Dependências externas | 0 |
| Tempo de inicialização | < 5ms (compilação dos regex) |
| Tempo por tradução (1ª vez) | < 1ms |
| Tempo por tradução (cache hit) | < 0,01ms |

---

*Documento atualizado — IDE hein · Agosto 2026*
