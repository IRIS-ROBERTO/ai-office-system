# IRIS PhD Engineering Agent Standard

Este padrão define o comportamento esperado para elevar os times de agentes a uma operação de engenharia de software de nível premium.

## Princípios

1. Toda entrega versionável precisa deixar evidência verificável: arquivos, validação, commit e risco residual.
2. Nenhum agente é aprovado por fluência textual; aprovação depende de manifesto determinístico.
3. Todo especialista deve declarar hipótese, escopo, validação e limite da entrega.
4. Marketing e Dev seguem o mesmo rigor quando produzem artefatos versionáveis.
5. Segredos em diff ou commit bloqueiam a entrega automaticamente.

## Comportamento Esperado

- Planner: transforma pedido em contrato testável, com critérios de aceite mensuráveis.
- Frontend: entrega interface funcional, acessível, buildável e sem dependências implícitas.
- Backend: entrega contrato, validação de dados, testes e migração segura quando aplicável.
- QA: adiciona smoke/regressão reproduzível, não apenas opinião sobre qualidade.
- Security: revisa segredos, superfície de ataque e permissões.
- Docs: produz runbook e handoff operacional.
- Marketing: versiona brief, campanha, copy, calendário, pesquisa ou relatório quando houver artefato.

## Gates Obrigatórios

- Evidence Gate: `DELIVERY_EVIDENCE` parseável.
- Commit Gate: SHA real dentro de raiz autorizada.
- File Gate: arquivos declarados precisam estar no commit.
- Validation Gate: ao menos uma validação objetiva com resultado `passed`.
- Secret Gate: padrões de token no diff bloqueiam aprovação.
- Functional Gate: entregas web precisam ter assets reais e interação executável.

## Métricas de Maturidade

- aprovação por agente;
- falha por gate;
- retrabalho por subtarefa;
- tempo até manifesto aprovado;
- porcentagem de entregas com commit;
- porcentagem de entregas com validação funcional;
- incidentes de segurança detectados antes do commit.

## Critério de Nível PhD

Um time só é considerado nível PhD quando mantém, por janela móvel de 30 entregas:

- 95% ou mais de manifestos aprovados na primeira ou segunda tentativa;
- 100% de entregas versionáveis com commit verificável;
- 0 segredos em commits aprovados;
- 90% ou mais de entregas com validação objetiva adequada ao domínio;
- retrospectiva automática gerando melhoria concreta para falhas recorrentes.
