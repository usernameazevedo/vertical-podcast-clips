# Rúbrica de cortes — o que faz um corte funcionar na internet

Critérios comprovados de short-form (Reels / Shorts / TikTok). Cada corte é pontuado de
0 a 10 na escolha, e **precisa vir com uma justificativa** (coluna `why` no cuts.tsv):
o critério pode ser diferente de um corte pro outro, mas o porquê é obrigatório.

## Portão de entrada (pass/fail — antes de pontuar)
- **Tema:** bate com o tema pedido na sessão (perguntar sempre quantos cortes e qual tema).
- **Mercado financeiro:** trade, dinheiro, patrimônio, investimento, psicologia do
  trader/investidor, gestão de risco. Se não for, descarta — nota não importa.

## Os 5 critérios (0 a 2 cada → total 0-10)

1. **Gancho (hook) nos primeiros 1-3s** — abre com algo que prende: pergunta, número
   concreto, afirmação contrária ao senso comum, ou tensão. Nada de "então, né, tipo...".
2. **Autoexplicativo (standalone)** — dá pra entender sem ter ouvido o episódio. Uma ideia
   clara, sem depender de contexto que ficou pra trás.
3. **Payoff / tensão** — tem uma virada, um insight, uma conclusão ou emoção. Constrói e
   entrega. Corte morno (sem clímax) não segura.
4. **Citável (quotable)** — tem uma frase forte que resume o corte e vira legenda/thumbnail.
   Ex.: "Dinheiro é igual antibiótico: ferramenta, não finalidade."
5. **Começar e terminar inteiro + ritmo** — o corte deve **começar no início de uma frase
   e terminar no fim de uma frase** (nunca no meio da ideia). Sem enrolação no início.
   **Duração é livre:** se o conteúdo justificar, o corte pode ser longo — não penalizar
   tamanho. O que importa é o trecho ser um pensamento completo e sem enrolação.

## Contexto completo e cortes costurados (REGRA)
- **Prefira contexto completo:** cortes de **1 a 2 minutos são bem-vindos** quando entregam
  a ideia inteira (setup + desenvolvimento + payoff), não só a frase de efeito solta.
- **Costurar trechos (stitch):** se dois ou mais pedaços **próximos e complementares**
  contam juntos uma história melhor, junte-os num único corte pela coluna `segments` do
  cuts.tsv (`ini->fim;ini->fim`). O `render.py` concatena os trechos num vídeo só e o
  `.srt` acompanha a costura. Use quando os pedaços se completam (ex.: a tese + a analogia
  que a ilustra), não para emendar assuntos diferentes.

## Como usar a nota
- **8-10:** corte forte, publica.
- **6-7:** bom, mas melhora com ajuste de início/fim (mexer nos timestamps).
- **< 6:** provavelmente descartar ou reescolher o trecho.

## Justificativa (obrigatória)
Na coluna `why` do cuts.tsv, escreva em 1 linha por que ESTE corte foi escolhido —
qual critério ele acerta em cheio. Ex.: "hook forte + frase citável"; "payoff emocional
do drawdown na FTX"; "número concreto (6% vs 8%) prende e é autoexplicativo".

## Validação mecânica (validate.py)
O `validate.py` checa automaticamente o que dá pra medir sem julgamento — se o corte
**começa e termina numa frase inteira**, densidade de fala (dead air) e silêncio no
início. Duração aparece só como informação (não é penalidade). Ele **não substitui** a
rúbrica; é um cinto de segurança contra erros óbvios (começar/terminar no meio da frase,
silêncio no início).
