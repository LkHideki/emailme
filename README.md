# Projeto de Envio de Email Automático com Python

Este projeto utiliza Python para enviar emails automaticamente através do servidor SMTP do Gmail. É um código curto e simples, escrito de forma a ser facilmente compreendido e modificado para atender às suas necessidades específicas.

## Dependências

Este projeto depende das seguintes bibliotecas Python:

- `os`
- `smtplib`
- `email.mime.multipart`
- `email.mime.text`
- `dotenv`

Você pode instalar todas as dependências necessárias ativando o seu ambiente virtual e executando o seguinte comando:

```bash
pip install -r requirements.txt
```

## Configuração

Para usar este projeto, você precisa configurar algumas variáveis de ambiente. Crie um arquivo `.env` na raiz do projeto e adicione a seguinte variável:

```
SENHA_DE_APP_GMAIL=sua_senha_de_app
```

Substitua `sua_senha_de_app` pela senha do aplicativo que você gerou para sua conta do Gmail.

## Uso

Para usar este projeto, importe a função `email_me` do arquivo `emailme.py` e chame-a com os parâmetros desejados. Aqui está um exemplo:

```python
from emailme import email_me

email_me("seu_email@gmail.com", "Assunto do Email", "Corpo do Email")
```

Substitua `seu_email@gmail.com`, `Assunto do Email` e `Corpo do Email` pelos valores desejados.

