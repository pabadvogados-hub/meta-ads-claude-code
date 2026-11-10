---
name: criar-campanha-meta
description: Monta uma campanha de anúncios na Meta (clique para WhatsApp) para escritório de advocacia, do documento do público-alvo até a campanha criada PAUSADA, respeitando o Provimento 205/2021 da OAB. Use quando o usuário pedir para criar, montar ou subir campanha, anúncio, tráfego pago ou Meta Ads.
---

# Criar campanha na Meta (advocacia, clique para WhatsApp)

Siga na ordem. Uma etapa por vez, confirmando com o usuário antes de passar para a próxima.
Ferramenta: `python meta_ads.py` (veja CLAUDE.md para as regras de segurança).

## 0. Conferir o ambiente
Rode `python meta_ads.py testar`. Se faltar token, página ou permissão, pare e mande o usuário ao README (passo 3).
Se `META_PAGE_ID` estiver vazio, rode `paginas` e ajude a escolher.

## 1. Público-alvo (documento-chave)
Abra `modelos/documento_chave_publico_alvo.md`. Se estiver vazio, preencha conversando: UMA pergunta por vez,
em linguagem do cliente (não do processo). Salve preenchido em `campanhas/documento_chave.md`.
Sem esse documento os criativos saem desajustados.

## 2. Oferta em uma frase + 4 filtros
Molde: `[Quem] que [está passando por qual problema] e [o que perde esta semana por causa disso]`.
Filtros (se algum for "não", volta para a frase): dói hoje? decide sozinho? o honorário cabe no bolso? você resolve em escala?
Mostre a frase e o resultado dos filtros.

## 3. Roteiros de vídeo (Provimento 205)
Gere dois roteiros do MESMO conteúdo, o usuário grava (celular na vertical, uma tomada):
- Curto, 20-25 s: 0-3 s gancho com a dor; 3-15 s explicação (o que é, por que acontece, o que a lei diz); 15-22 s convite ("Se é o seu caso, toque no botão e mande sua dúvida").
- Longo, 40-45 s: o mesmo, com um exemplo a mais no meio. Sem garantir resultado.
Use `modelos/roteiro_video.md`. Releia contra `modelos/provimento_205_checklist.md`.

## 4. Montar o JSON
Copie `exemplos/campanha_exemplo.json` para `campanhas/<nome>.json` e preencha:
- um **conjunto por vídeo** (se puser os dois no mesmo, a Meta escolhe um favorito e o outro nunca é testado);
- R$ 15 a 30 por dia por conjunto;
- **um código por anúncio** (A1, A2...) no fim da `mensagem_inicial` do anúncio, ex.: `... [A1]`;
- locais: use `python meta_ads.py buscar-local "Cidade"` para confirmar que o nome existe;
- vídeos em `midia/` (só o nome do arquivo no JSON);
- texto principal curto, informativo, sem promessa, sem preço, sem "grátis".

## 5. Validar e mostrar o plano
`python meta_ads.py validar campanhas/<nome>.json` - corrija os erros e os alertas da OAB.
`python meta_ads.py criar campanhas/<nome>.json` (sem --executar) - mostre o plano, orçamento somado e o teto.
Pergunte: "Posso criar? Vai ficar tudo pausado."

## 6. Criar
`python meta_ads.py criar campanhas/<nome>.json --executar`
Se a Meta recusar algo, leia o erro, traduza e conserte o JSON (causas comuns abaixo).

## 7. Conferir e ativar
Peça ao usuário abrir o Gerenciador de Anúncios e conferir: vídeo certo em cada conjunto, texto, público, número do WhatsApp
e mensagem pré-preenchida com o código. Só com o "pode ativar" dele: `ativar <id da campanha> --confirmo`
(e conjuntos/anúncios, se estiverem pausados). Anote a data em que terminam os 7 dias de aprendizado.

## 8. Acompanhar
`python meta_ads.py relatorio --periodo last_7d` (por anúncio). A decisão é por **custo por contrato assinado**:
cruzar o código do anúncio com a planilha de leads. Pausar quem custa mais que o dobro do melhor; subir verba só
depois de pelo menos 3 contratos; nunca trocar vídeo na segunda semana "porque não deu resultado".

## Erros comuns
| Erro | O que fazer |
|---|---|
| `(#200)` / permissão | O token não tem `ads_management` ou a conta/página não foi atribuída ao usuário do sistema. README passo 3. |
| Página não aparece em `paginas` | No Business Manager: Usuários do sistema > Adicionar ativos > Páginas. |
| WhatsApp recusado no conjunto | O número precisa estar conectado à Página (Página > Configurações > Contas vinculadas > WhatsApp). |
| Vídeo "ainda processando" | Esperar uns minutos e rodar de novo; o vídeo já está na conta. Use o ID dele no JSON em vez do arquivo. |
| Cidade não encontrada | `buscar-local` e usar o nome exato; ou usar a região (estado). |
| Conta com pagamento pendente | Resolver no Gerenciador de Anúncios > Cobrança. |
