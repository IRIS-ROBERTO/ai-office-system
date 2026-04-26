export const scoutInsight = {
  "title": "Mem\u00f3ria e RAG",
  "description": "Sistemas de recupera\u00e7\u00e3o e persist\u00eancia de contexto para agentes",
  "recommendation": "Implementar 'daily_stock_analysis' para mem\u00f3ria persistente entre sess\u00f5es dos agentes \u2014 78 solu\u00e7\u00f5es de RAG encontradas.",
  "potential": {
    "score": 90,
    "viability": "alt\u00edssimo",
    "viability_color": "#f97316",
    "viability_icon": "\ud83d\udd25",
    "viability_label": "\ud83d\udd25 Potencial Alt\u00edssimo",
    "speed_impact": "Agentes com mem\u00f3ria persistente n\u00e3o repetem erros anteriores e reutilizam solu\u00e7\u00f5es validadas \u2014 aprendizado cont\u00ednuo sem retrabalho.",
    "pitch": "Knowledge Base inteligente como SaaS \u2014 empresas pagam para ter documentos, hist\u00f3rico e processos acess\u00edveis por agentes AI em tempo real. Recorr\u00eancia mensal garantida. Upsell: analytics de uso + relat\u00f3rios autom\u00e1ticos de intelig\u00eancia organizacional."
  },
  "summary": {
    "o_que_e": "S\u00e3o sistemas de embeddings e recupera\u00e7\u00e3o sem\u00e2ntica \u2014 como daily_stock_analysis, mempalace, WeKnora. Transformam textos em vetores num\u00e9ricos para encontrar informa\u00e7\u00f5es relevantes por similaridade de significado, n\u00e3o apenas por palavra-chave.",
    "para_que_serve": "Serve para dar mem\u00f3ria de longo prazo aos agentes IRIS: lembrar de projetos anteriores, decis\u00f5es t\u00e9cnicas j\u00e1 tomadas, padr\u00f5es de c\u00f3digo do reposit\u00f3rio, e contexto de tarefas passadas. Hoje os agentes 'esquecem tudo' a cada nova sess\u00e3o \u2014 RAG resolve isso.",
    "onde_usariamos": "No memory-gateway e no Supabase (que j\u00e1 est\u00e1 configurado no IRIS). Antes de executar uma tarefa, o agente consultaria o RAG: 'j\u00e1 fizemos algo parecido antes?' \u2014 e reutilizaria solu\u00e7\u00f5es anteriores em vez de reinventar do zero.",
    "o_que_implementariamos": "Pipeline RAG com 'daily_stock_analysis': ao concluir cada tarefa, salvar o resumo + c\u00f3digo gerado como vetores no Supabase. Ao iniciar nova tarefa, recuperar os 3 contextos mais similares e incluir no prompt do agente. Resultado pr\u00e1tico: agentes que aprendem com o hist\u00f3rico do projeto."
  },
  "projects": [
    {
      "id": "gh_1131513930",
      "title": "daily_stock_analysis",
      "name": "ZhuLinsen/daily_stock_analysis",
      "score": 87,
      "grade": "S",
      "url": "https://github.com/ZhuLinsen/daily_stock_analysis",
      "iris_fit": [
        "Orquestra\u00e7\u00e3o de agentes",
        "Integra\u00e7\u00e3o LLM",
        "RAG / Mem\u00f3ria"
      ],
      "combination_rationale": "",
      "project_names": [],
      "source": "github"
    },
    {
      "id": "gh_1201656210",
      "title": "mempalace",
      "name": "MemPalace/mempalace",
      "score": 87,
      "grade": "S",
      "url": "https://github.com/MemPalace/mempalace",
      "iris_fit": [
        "Integra\u00e7\u00e3o LLM",
        "MCP / Ferramentas"
      ],
      "combination_rationale": "",
      "project_names": [],
      "source": "github"
    },
    {
      "id": "gh_1024118326",
      "title": "WeKnora",
      "name": "Tencent/WeKnora",
      "score": 86,
      "grade": "S",
      "url": "https://github.com/Tencent/WeKnora",
      "iris_fit": [
        "Orquestra\u00e7\u00e3o de agentes",
        "Integra\u00e7\u00e3o LLM",
        "RAG / Mem\u00f3ria"
      ],
      "combination_rationale": "",
      "project_names": [],
      "source": "github"
    },
    {
      "id": "gh_605673387",
      "title": "FastGPT",
      "name": "labring/FastGPT",
      "score": 85,
      "grade": "S",
      "url": "https://github.com/labring/FastGPT",
      "iris_fit": [
        "Orquestra\u00e7\u00e3o de agentes",
        "Integra\u00e7\u00e3o LLM",
        "RAG / Mem\u00f3ria",
        "MCP / Ferramentas",
        "Automa\u00e7\u00e3o de workflows"
      ],
      "combination_rationale": "",
      "project_names": [],
      "source": "github"
    },
    {
      "id": "gh_221654678",
      "title": "haystack",
      "name": "deepset-ai/haystack",
      "score": 85,
      "grade": "S",
      "url": "https://github.com/deepset-ai/haystack",
      "iris_fit": [
        "Orquestra\u00e7\u00e3o de agentes",
        "Integra\u00e7\u00e3o LLM",
        "RAG / Mem\u00f3ria"
      ],
      "combination_rationale": "",
      "project_names": [],
      "source": "github"
    }
  ]
};
