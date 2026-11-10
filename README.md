# Pacote Meta Ads para o Claude Code

Com este pacote o Claude Code monta, sobe e acompanha as **suas** campanhas de anúncio no Facebook e Instagram
(clique para WhatsApp), na **sua** conta, com travas de segurança e checagem do Provimento 205/2021 da OAB.

```
Você conversa  ->  Claude Code escreve o JSON da campanha  ->  meta_ads.py cria na Meta (tudo PAUSADO)
                                                                 ->  você confere  ->  você manda ativar
```

## O que vem no pacote
| Arquivo | Para quê |
|---|---|
| `meta_ads.py` | A ferramenta: cria campanha/conjuntos/anúncios, sobe vídeo, relatório, pausar/ativar |
| `CLAUDE.md` | As regras que o Claude Code segue nesta pasta (segurança + OAB) |
| `.claude/skills/criar-campanha-meta` | O passo a passo que o Claude Code segue para montar a campanha |
| `.claude/commands` | Atalhos: `/campanha`, `/relatorio`, `/oab` |
| `modelos/` | Documento-chave do público, roteiro de vídeo, checklist do Provimento 205 |
| `exemplos/campanha_exemplo.json` | Campanha de exemplo: 2 vídeos (curto x longo), 1 conjunto por vídeo |
| `midia/` | Onde ficam seus vídeos e imagens |
| `.env.example` | Modelo da configuração (token, conta, página, WhatsApp) |

## Passo a passo

### 1. Instalar (uma vez)
- Python 3.9+ (python.org) e o Claude Code (plano Pro ou superior).
- Abra um terminal **dentro desta pasta** e rode:
```bash
pip install -r requirements.txt
```

### 2. Pré-requisitos na Meta
- Uma **Página do Facebook** do escritório (e, de preferência, o Instagram profissional ligado a ela).
- Uma **conta de anúncio** com forma de pagamento cadastrada.
- O **WhatsApp** que vai receber os leads conectado à Página: Página > Configurações > Contas vinculadas > WhatsApp.
- Um **Business Manager** (business.facebook.com). Se não tiver, crie: é gratuito.

### 3. Gerar o token (uma vez; ele não expira)
1. **developers.facebook.com** > Meus Apps > Criar app > tipo **Empresa** (Business). Dê um nome e vincule ao seu Business Manager.
2. **business.facebook.com** > Configurações do Negócio > **Usuários > Usuários do sistema > Adicionar**. Nome livre, função **Admin**.
3. Com o usuário selecionado, **Adicionar ativos**:
   - **Contas de anúncio** > a sua > controle total (Gerenciar campanhas);
   - **Páginas** > a sua > controle total.
4. **Gerar novo token** > escolha o app do passo 1 > validade **Nunca** > marque as permissões:
   `ads_management`, `ads_read`, `business_management`, `pages_show_list`, `pages_read_engagement`.
5. Copie o token (aparece uma vez só).

> **O token é o acesso ao seu dinheiro de anúncio.** Não mande por WhatsApp, não cole em conversa com ninguém,
> não suba o `.env` no GitHub (já está no `.gitignore`). Se vazar: Configurações do Negócio > Usuário do sistema >
> Revogar tokens, e gere outro.

### 4. Configurar (um comando)
```bash
python meta_ads.py configurar
```
Cole o token (não aparece na tela) e informe o WhatsApp. O script descobre sozinho a conta de anúncio, a Página e o
Instagram, grava o `.env` e confere tudo. Depois:
```bash
python meta_ads.py testar     # deve mostrar suas permissões, conta e página
```
(Se preferir à mão: `copy .env.example .env` e preencha. `contas` e `paginas` mostram os IDs.)

### 5. Abrir o Claude Code e montar a campanha
Na pasta do pacote, rode `claude` e cole o conteúdo de `PROMPT_DE_INICIO.md` (ou digite `/campanha`).
O Claude Code vai:
1. conferir o ambiente;
2. te ajudar a preencher o **documento-chave do público** (uma pergunta por vez);
3. escrever a **oferta em uma frase** e passar pelos 4 filtros;
4. fazer os **roteiros dos dois vídeos** (curto e longo) já conferidos com o Provimento 205;
5. montar o JSON (um conjunto por vídeo, um código por anúncio: A1, A2...);
6. te mostrar o **plano** e, com o seu "pode criar", **criar tudo pausado**.

Coloque os vídeos gravados em `midia/` antes da criação.

### 6. Conferir e ativar
Abra o **Gerenciador de Anúncios** e confira vídeo, texto, público, número e a mensagem do WhatsApp (ela termina com o código, ex.: `[A1]`).
Estando certo, peça ao Claude Code: "pode ativar". Ele roda `python meta_ads.py ativar <id> --confirmo`.

### 7. Os 7 primeiros dias
**Não troque vídeo nem texto.** Só a verba. Cada mexida reinicia o aprendizado e você paga a curva de novo.

### 8. Acompanhar e decidir
`/relatorio` no Claude Code, ou `python meta_ads.py relatorio --periodo last_7d`.
Registre na planilha o código (A1, A2) de cada lead e quantos assinaram. **Decida pelo custo por contrato assinado**, não pelo custo por lead.
- Pausar: gastou o bastante e não deu contrato, ou custa mais que o dobro do melhor.
- Subir verba: só depois de pelo menos 3 contratos.

## Travas de segurança
- Tudo é criado **PAUSADO**.
- `criar` sem `--executar` só mostra o plano.
- `ativar` exige `--confirmo`.
- A soma dos orçamentos diários não passa de `MAX_ORCAMENTO_DIARIO` (padrão R$ 100).
- Verificador do Provimento 205 antes de subir (pega o óbvio; **não substitui o advogado**).

## Problemas comuns
| Sintoma | Solução |
|---|---|
| `Falta instalar: pip install...` | Rode `pip install -r requirements.txt` |
| `(#200)` ou "permissão" | Token sem `ads_management` ou conta/página não atribuída ao usuário do sistema (passo 3.3) |
| `paginas` vem vazio | Atribua a Página como ativo do usuário do sistema |
| Conjunto recusado por causa do WhatsApp | O número precisa estar conectado à Página (passo 2) |
| "Cidade não encontrada" | `python meta_ads.py buscar-local "nome"` e use o nome exato, ou use o estado |
| Conta com pagamento pendente | Gerenciador de Anúncios > Cobrança |
| Erro estranho da Meta | Cole a mensagem no Claude Code: ele traduz e conserta o JSON |

## Aviso
Ferramenta de apoio. Você é o responsável pelo conteúdo dos seus anúncios e pelo cumprimento do Código de Ética
e do Provimento 205/2021. Os nomes de telas e botões da Meta mudam com frequência; o que importa em cada passo é o resultado descrito.
