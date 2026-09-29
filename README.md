# emailme

Envia emails para você mesmo (ou para outros destinatários) via SMTP. O padrão é o
servidor do Gmail com STARTTLS. Pode ser usado como biblioteca Python ou pela linha
de comando.

Requer Python 3.14 e [uv](https://docs.astral.sh/uv/).

## Instalação

```bash
uv sync                 # cria .venv com Python 3.14 e instala dependências + dev
```

Para usar só a CLI, sem clonar o repositório:

```bash
uv tool install git+https://github.com/LkHideki/emailme
```

## Configuração

Copie `.env.example` para `.env` e preencha a senha de app do Gmail
(gerada em <https://myaccount.google.com/apppasswords>):

```
EMAILME_PASSWORD=sua_senha_de_app
EMAILME_USERNAME=seu_email@gmail.com
```

O `.env` é procurado no diretório atual e, se não existir, nos diretórios acima. Variáveis já definidas no ambiente
têm precedência sobre o arquivo.

| Variável              | Padrão           | Descrição                                          |
| --------------------- | ---------------- | -------------------------------------------------- |
| `EMAILME_PASSWORD`    | —                | Senha de app (obrigatória)                         |
| `SENHA_DE_APP_GMAIL`  | —                | Nome antigo da senha, ainda aceito                 |
| `EMAILME_USERNAME`    | —                | Remetente/usuário SMTP padrão da CLI               |
| `EMAILME_SMTP_HOST`   | `smtp.gmail.com` | Servidor SMTP                                      |
| `EMAILME_SMTP_PORT`   | `587`            | Porta                                              |
| `EMAILME_STARTTLS`    | `true`           | Usa STARTTLS (com verificação de certificado)      |
| `EMAILME_TIMEOUT`     | `30`             | Timeout de conexão, em segundos                    |

## Uso como biblioteca

A função original continua funcionando do mesmo jeito:

```python
from emailme import email_me

email_me("seu_email@gmail.com", "Assunto do Email", "Corpo do Email")
```

Para mais controle, monte as peças diretamente:

```python
from emailme import Mailer, SmtpSettings, SmtpTransport

settings = SmtpSettings(username="eu@gmail.com", password="senha-de-app")
mailer = Mailer(SmtpTransport(settings), sender="eu@gmail.com")
mailer.send(subject="Backup concluído", body="Tudo certo.", to=["time@example.com"])
```

Em testes do seu próprio código, troque o transporte por um em memória:

```python
from emailme import InMemoryTransport, email_me

transport = InMemoryTransport()
email_me("eu@gmail.com", "Oi", transport=transport)
assert transport.outbox[0]["Subject"] == "Oi"
```

Erros levantados (todos herdam de `EmailMeError`):

- `ConfigurationError`: configuração ausente ou inválida. Também é um `EnvironmentError`,
  como na versão anterior.
- `InvalidEmailError`: endereço ou assunto inválido (inclui tentativa de header injection).
  Também é um `ValueError`.
- `DeliveryError`: falha de rede ou do servidor SMTP.
- `AuthenticationError`: credenciais recusadas (subclasse de `DeliveryError`).

## Uso pela linha de comando

```bash
emailme "Corpo da mensagem" -s "Assunto"
emailme -s "Relatório" --to a@example.com --to b@example.com "Corpo"
make build 2>&1 | emailme -s "Resultado do build" -      # corpo lido do stdin
emailme --dry-run "teste"                                # mostra a mensagem, não envia
uv run python -m emailme --help
```

Códigos de saída: `0` sucesso, `1` falha de entrega, `2` uso/entrada inválida,
`3` configuração ausente.

## Arquitetura

```
src/emailme/
├── errors.py     hierarquia de exceções
├── config.py     SmtpSettings: configuração imutável e validada; leitura de env isolada
├── message.py    Email: modelo de domínio imutável + conversão para MIME
├── transport.py  protocolo Transport; SmtpTransport (real) e InMemoryTransport
├── service.py    Mailer: orquestra criação e envio
├── api.py        email_me(): fachada compatível com a versão original
└── cli.py        interface de linha de comando (argparse)
```

As dependências apontam para dentro: `cli`/`api` → `service` → `message`/`transport` →
`config`/`errors`. Só `transport.py` faz I/O de rede e só `api.py`/`cli.py` leem o
ambiente, então o resto é testável sem mocks de rede.

Mudanças em relação à versão anterior:

- `load_dotenv()` deixou de rodar no import e não modifica mais `os.environ`.
- A biblioteca não usa mais `print`; registra em `logging` (logger `emailme`). A mensagem
  "Email enviado com sucesso!" agora é exibida pela CLI.
- STARTTLS passou a verificar o certificado do servidor (`ssl.create_default_context()`).
- Endereços e assunto são validados, o que bloqueia header injection.
- Falhas de SMTP viram exceções do pacote, com a original encadeada em `__cause__`.

## Testes

```bash
uv run pytest                           # tudo: doctests + todas as suítes
uv run pytest --cov                     # com cobertura (mínimo 95%)
uv run pytest -m unit                   # só uma suíte
uv run pytest --hypothesis-profile=ci   # mais exemplos nos testes de propriedade
```

| Suíte          | Pasta                | O que cobre                                                         |
| -------------- | -------------------- | ------------------------------------------------------------------- |
| doctests       | `src/emailme/`       | Exemplos das docstrings                                             |
| `unit`         | `tests/unit/`        | Cada módulo isolado, com dublês (`FakeSMTP`, `InMemoryTransport`)   |
| `property`     | `tests/property/`    | Invariantes com Hypothesis (roundtrip MIME, validação, config)      |
| `contract`     | `tests/contract/`    | Os mesmos testes rodando contra todas as implementações de Transport |
| `integration`  | `tests/integration/` | `SmtpTransport` contra um servidor SMTP local real (aiosmtpd)       |
| `e2e`          | `tests/e2e/`         | A CLI instalada rodando em subprocesso, contra o servidor local     |

Nenhum teste acessa a internet: integração e e2e sobem um servidor `aiosmtpd` em
`127.0.0.1` com autenticação.

## Qualidade

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy                 # modo strict, cobre src/ e tests/
```

O workflow `.github/workflows/ci.yml` roda lint, tipos, cada suíte de testes em
paralelo, cobertura e um smoke test do wheel gerado por `uv build`.
