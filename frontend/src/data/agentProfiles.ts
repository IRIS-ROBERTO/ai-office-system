export interface AgentProfile {
  codename: string;
  title: string;
  summary: string;
  mission: string;
  experience: string;
  signature: string;
  personality: string[];
  strengths: string[];
  toolkit: string[];
  careerHighlights: string[];
}

export const AGENT_PROFILE_REGISTRY: Record<string, AgentProfile> = {
  dev_planner_01: {
    codename: 'ATLAS',
    title: 'Software Architect & Planning Lead',
    summary: 'Traduz objetivos difusos em arquitetura, backlog executavel e sequenciamento tecnico sem desperdicio.',
    mission: 'Garantir que o time de engenharia avance com clareza, escopo controlado e criterio tecnico alto.',
    experience: 'Especialista em decomposicao de problemas, arquitetura de produto e priorizacao de trade-offs.',
    signature: 'Planeja primeiro, reduz risco cedo e protege a coerencia do sistema inteiro.',
    personality: ['estrategico', 'metodico', 'frio sob pressao', 'orientado a impacto'],
    strengths: ['arquitetura', 'planejamento de sprint', 'sequenciamento de tarefas', 'governanca tecnica'],
    toolkit: ['LangGraph', 'CrewAI', 'Python', 'arquitetura distribuida', 'design de prompts'],
    careerHighlights: [
      'Estruturou o fluxo senior_planning -> quality_gate do escritorio.',
      'Define os contratos entre subtarefas antes do handoff tecnico.',
      'Age como guardiao de escopo para entregas de engenharia.'
    ],
  },
  dev_frontend_01: {
    codename: 'PIXEL',
    title: 'Frontend Engineer & Experience Builder',
    summary: 'Cuida da camada visual com foco em clareza, responsividade e interfaces que comuniquem estado real.',
    mission: 'Transformar o runtime dos agentes em experiencia visual inteligivel e elegante.',
    experience: 'Especialista em React, TypeScript, animacao de interface e composicao visual orientada a estado.',
    signature: 'Nao aceita UI genérica nem estado visual desconectado do backend.',
    personality: ['expressivo', 'detalhista', 'obsessivo por UX', 'iterativo'],
    strengths: ['React', 'TypeScript', 'PixiJS', 'layout responsivo', 'hidratação de estado'],
    toolkit: ['React', 'Vite', 'PixiJS', 'Zustand', 'CSS-in-JS'],
    careerHighlights: [
      'Materializou o escritorio visual multiagente em tempo real.',
      'Conecta sinais do backend a feedback visual compreensivel.',
      'Defende legibilidade visual mesmo sob alto volume de eventos.'
    ],
  },
  dev_backend_01: {
    codename: 'FORGE',
    title: 'Backend Engineer & Systems Integrator',
    summary: 'Constrói os fluxos de API, integra serviços e mantém o runtime operacional sob carga.',
    mission: 'Entregar pipelines confiaveis entre orquestracao, eventos, execucao e persistencia.',
    experience: 'Especialista em FastAPI, integrações backend-first, telemetria de runtime e contratos de API.',
    signature: 'Prefere sistemas previsiveis, observaveis e com superficie de erro pequena.',
    personality: ['pragmatico', 'robusto', 'disciplinado', 'orientado a confiabilidade'],
    strengths: ['FastAPI', 'integração de serviços', 'event bus', 'observabilidade', 'contratos REST'],
    toolkit: ['FastAPI', 'Redis', 'Pydantic', 'asyncio', 'Supabase'],
    careerHighlights: [
      'Conecta os times de agentes ao backend operacional.',
      'Mantém os endpoints centrais de tasks, agents e health.',
      'Fortalece o runtime quando o sistema entra em execução real.'
    ],
  },
  dev_qa_01: {
    codename: 'SHERLOCK',
    title: 'QA Engineer & Runtime Auditor',
    summary: 'Busca inconsistencias, regressões e comportamentos silenciosamente quebrados antes da entrega.',
    mission: 'Impedir que falhas de fluxo, contrato ou interface escapem para a camada final.',
    experience: 'Especialista em cenarios de validacao, stress tests e leitura critica de comportamento.',
    signature: 'Nao confia em aparencia de sucesso sem evidencia reproduzivel.',
    personality: ['investigativo', 'cauteloso', 'criterioso', 'persistente'],
    strengths: ['testes E2E', 'stress testing', 'reproducibilidade', 'analise de regressao'],
    toolkit: ['scripts de validacao', 'health checks', 'testes de fluxo', 'observacao de logs'],
    careerHighlights: [
      'Valida se o escritorio visual bate com o runtime real.',
      'Expõe falhas de contrato entre backend e frontend.',
      'Ajuda a transformar evidencias em entrega auditavel.'
    ],
  },
  dev_security_01: {
    codename: 'AEGIS',
    title: 'Security Engineer & Risk Gatekeeper',
    summary: 'Observa superficie de risco, endurece acessos e reduz exposicao operacional do sistema.',
    mission: 'Garantir que a automacao dos agentes não comprometa seguranca, chaves ou integridade do repositório.',
    experience: 'Especialista em revisao de riscos, configuracao segura e blindagem de fluxos automatizados.',
    signature: 'Protege o sistema antes que vulnerabilidades virem incidentes.',
    personality: ['reservado', 'vigilante', 'analitico', 'intransigente com risco'],
    strengths: ['hardening', 'controle de segredos', 'avaliacao de risco', 'segurança operacional'],
    toolkit: ['GitHub token hygiene', 'políticas de acesso', 'revisão de superficie de ataque', 'logs'],
    careerHighlights: [
      'Avalia risco em automacoes com acesso a repositório e APIs.',
      'Revisa caminhos inseguros antes de serem padronizados.',
      'Atua como contenção quando a entrega acelera demais.'
    ],
  },
  dev_docs_01: {
    codename: 'LORE',
    title: 'Technical Writer & Knowledge Curator',
    summary: 'Converte decisões, fluxos e comportamentos do sistema em documentação operacional legivel.',
    mission: 'Garantir que o conhecimento do escritorio nao dependa de memoria oral ou contexto perdido.',
    experience: 'Especialista em documentação técnica, contexto de produto e manutenção de memória operacional.',
    signature: 'Documenta para reduzir atrito, onboarding e ambiguidade de execução.',
    personality: ['didatico', 'calmo', 'organizado', 'preciso'],
    strengths: ['documentação técnica', 'runbooks', 'memória de projeto', 'explicações de arquitetura'],
    toolkit: ['Markdown', 'context capture', 'docs de fluxo', 'guia operacional'],
    careerHighlights: [
      'Consolida entendimento de arquitetura e decisões de runtime.',
      'Mantém a narrativa do projeto atualizada para operação.',
      'Ajuda novos operadores a entender o sistema com menos atrito.'
    ],
  },
  mkt_research_01: {
    codename: 'ORACLE',
    title: 'Market Research Analyst',
    summary: 'Mapeia cenarios, concorrencia e sinais de mercado para orientar posicionamento com lastro.',
    mission: 'Trazer inteligencia externa que aumente a qualidade das decisões de marketing.',
    experience: 'Especialista em leitura de mercado, repertorio competitivo e síntese de contexto.',
    signature: 'Prefere evidência, contexto e leitura de padrão antes de opinião.',
    personality: ['curioso', 'sintetico', 'racional', 'atento a sinais fracos'],
    strengths: ['pesquisa', 'benchmarking', 'análise competitiva', 'sintese estratégica'],
    toolkit: ['desk research', 'análise de cenário', 'mapeamento competitivo', 'insights'],
    careerHighlights: [
      'Abre o campo antes das decisões de campanha.',
      'Identifica lacunas e oportunidades de posicionamento.',
      'Ajuda o time MKT a agir com contexto, não com impulso.'
    ],
  },
  mkt_strategy_01: {
    codename: 'MAVEN',
    title: 'Marketing Strategist',
    summary: 'Transforma pesquisa em direção de campanha, proposta de valor e plano de execução de go-to-market.',
    mission: 'Garantir que narrativa, canal e timing conversem com o objetivo de negócio.',
    experience: 'Especialista em posicionamento, estratégia de campanha e desenho de iniciativas multicanal.',
    signature: 'Costura contexto, mensagem e distribuição num plano coerente.',
    personality: ['assertivo', 'estruturado', 'visionario', 'orientado a tese'],
    strengths: ['posicionamento', 'go-to-market', 'planejamento de campanha', 'mensageria'],
    toolkit: ['frameworks de estratégia', 'campanhas', 'ICP', 'narrativa de marca'],
    careerHighlights: [
      'Coordena o raciocínio de campanha do time MKT.',
      'Converte sinais de pesquisa em direção acionável.',
      'Protege coerencia entre mensagem e objetivo comercial.'
    ],
  },
  mkt_content_01: {
    codename: 'NOVA',
    title: 'Content Creator & Copywriter',
    summary: 'Escreve com ritmo, clareza e intenção comercial sem perder identidade de marca.',
    mission: 'Transformar estratégia em mensagens memoráveis, úteis e publicáveis.',
    experience: 'Especialista em copy, conteúdo editorial, roteiros curtos e narrativa de campanha.',
    signature: 'Procura frase forte, ritmo correto e clareza de conversão.',
    personality: ['criativo', 'verbal', 'sensivel a tom', 'rapido em iteração'],
    strengths: ['copywriting', 'conteúdo editorial', 'roteiros', 'headline crafting'],
    toolkit: ['copy', 'content planning', 'brand voice', 'storytelling'],
    careerHighlights: [
      'Dá voz pública às hipóteses do time MKT.',
      'Traduz direção estratégica em peças concretas.',
      'Equilibra persuasão com legibilidade e identidade.'
    ],
  },
  mkt_seo_01: {
    codename: 'APEX',
    title: 'SEO Specialist',
    summary: 'Ajusta linguagem, estrutura e intenção de conteúdo para capturar demanda orgânica de forma disciplinada.',
    mission: 'Fazer com que o conteúdo encontre o mercado antes de depender apenas de mídia.',
    experience: 'Especialista em arquitetura de conteúdo, intenção de busca e otimização orgânica.',
    signature: 'Busca relevância sustentavel e ganho incremental consistente.',
    personality: ['tecnico', 'paciente', 'orientado a sinal', 'criterioso'],
    strengths: ['SEO on-page', 'clusters de conteúdo', 'keyword mapping', 'otimização semântica'],
    toolkit: ['SEO', 'metadata', 'SERP intent', 'estrutura de páginas'],
    careerHighlights: [
      'Ajuda o escritorio a crescer por descoberta orgânica.',
      'Evita que conteúdo bom seja invisível.',
      'Conecta produção editorial a demanda de busca real.'
    ],
  },
  mkt_social_01: {
    codename: 'PULSE',
    title: 'Social Media Manager',
    summary: 'Adapta mensagens para cadência social, reação rápida e formato nativo de distribuição.',
    mission: 'Manter a presença viva, responsiva e alinhada com o ritmo dos canais sociais.',
    experience: 'Especialista em posts curtos, cadência de canal, distribuição e atenção em tempo real.',
    signature: 'Valoriza timing, clareza e energia de publicação.',
    personality: ['energetico', 'agil', 'adaptativo', 'focado em ritmo'],
    strengths: ['social copy', 'cadência de canal', 'distribuição', 'adaptação de mensagem'],
    toolkit: ['social media', 'post design direction', 'content cadence', 'microcopy'],
    careerHighlights: [
      'Converte campanhas em presença social contínua.',
      'Ajusta mensagem ao formato e velocidade de cada canal.',
      'Mantém a camada pública em movimento.'
    ],
  },
  mkt_analytics_01: {
    codename: 'PRISM',
    title: 'Marketing Analytics Expert',
    summary: 'Lê métricas, identifica padrões e transforma desempenho em feedback acionável para o time.',
    mission: 'Fechar o loop entre ação de marketing e aprendizado real do sistema.',
    experience: 'Especialista em leitura de performance, interpretação de sinais e correção de rota baseada em dados.',
    signature: 'Não aceita campanha sem leitura posterior e sem decisão derivada.',
    personality: ['quantitativo', 'frio', 'preciso', 'orientado a causalidade'],
    strengths: ['analytics', 'métricas de campanha', 'leitura de tendência', 'feedback loops'],
    toolkit: ['dashboards', 'performance review', 'funnel thinking', 'reporting'],
    careerHighlights: [
      'Fecha o ciclo entre execução e aprendizado do time MKT.',
      'Traduz números em ação concreta.',
      'Ajuda campanhas a melhorar por iteração e não por aposta.'
    ],
  },
};

const DEFAULT_PROFILE: AgentProfile = {
  codename: 'IRIS',
  title: 'Autonomous Specialist',
  summary: 'Agente especializado do escritorio IRIS.',
  mission: 'Executar sua função com consistência e alto nível operacional.',
  experience: 'Perfil geral de agente autônomo.',
  signature: 'Trabalha com autonomia orientada a contrato.',
  personality: ['consistente', 'especializado'],
  strengths: ['execução', 'adaptação'],
  toolkit: ['IA', 'fluxos automatizados'],
  careerHighlights: ['Registrado no runtime do escritorio.'],
};

export function getAgentProfile(agentId: string, role?: string): AgentProfile {
  const direct = AGENT_PROFILE_REGISTRY[agentId];
  if (direct) return direct;

  const normalizedRole = (role || '').toLowerCase();
  return {
    ...DEFAULT_PROFILE,
    codename: normalizedRole ? normalizedRole.toUpperCase() : DEFAULT_PROFILE.codename,
    title: normalizedRole ? `${normalizedRole} specialist` : DEFAULT_PROFILE.title,
  };
}

export const AGENT_CODENAMES = Object.fromEntries(
  Object.entries(AGENT_PROFILE_REGISTRY).map(([agentId, profile]) => [agentId, profile.codename])
) as Record<string, string>;
