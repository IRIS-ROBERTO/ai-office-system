export const scoutInsight = {
  "title": "Aprimoramento de LLM",
  "description": "Modelos e integra\u00e7\u00f5es que melhoram as capacidades de linguagem dos agentes",
  "recommendation": "Avaliar 'claude-mem' como LLM alternativo/complementar para os agentes IRIS \u2014 64 modelos identificados.",
  "potential": {
    "score": 94,
    "viability": "alt\u00edssimo",
    "viability_color": "#f97316",
    "viability_icon": "\ud83d\udd25",
    "viability_label": "\ud83d\udd25 Potencial Alt\u00edssimo",
    "speed_impact": "Modelos especializados geram c\u00f3digo/an\u00e1lise com menor itera\u00e7\u00e3o humana \u2014 qualidade de sa\u00edda +40% vs. modelos gen\u00e9ricos.",
    "pitch": "LLM-as-a-Service com fine-tuning por nicho (jur\u00eddico, sa\u00fade, finan\u00e7as, e-commerce). Pricing por token com camada de seguran\u00e7a e compliance inclu\u00edda. Margem bruta alta (70%+). Barreira de entrada: curadoria de dados + expertise de deploy."
  },
  "summary": {
    "o_que_e": "S\u00e3o modelos de linguagem e integra\u00e7\u00f5es com provedores de IA \u2014 como claude-mem, hermes-agent, full-stack-ai-agent-template. Incluem LLMs locais (rodando no seu Ollama) e modelos cloud (via OpenRouter), cada um com diferentes perfis de velocidade, custo e qualidade.",
    "para_que_serve": "Serve para melhorar a qualidade das respostas dos agentes IRIS ou reduzir custo/lat\u00eancia. Diferentes tarefas precisam de diferentes modelos: c\u00f3digo exige precis\u00e3o, marketing exige criatividade, an\u00e1lise exige racioc\u00ednio longo.",
    "onde_usariamos": "No `brain_router.py` \u2014 o roteador central de modelos do IRIS. Cada perfil de agente (dev, marketing, scout, qa) pode apontar para o modelo mais adequado. Um novo modelo pode ser adicionado como op\u00e7\u00e3o local no Ollama ou cloud no OpenRouter.",
    "o_que_implementariamos": "Adicionar 'claude-mem' como novo modelo dispon\u00edvel no brain_router, criar um perfil de agente espec\u00edfico (ex: 'coder_v2') apontando para ele, e validar com um smoke test de gera\u00e7\u00e3o de c\u00f3digo e racioc\u00ednio. Resultado: agentes mais inteligentes para tarefas espec\u00edficas, sem custo extra."
  },
  "projects": [
    {
      "id": "gh_1048065319",
      "title": "claude-mem",
      "name": "thedotmack/claude-mem",
      "score": 85,
      "grade": "S",
      "url": "https://github.com/thedotmack/claude-mem",
      "iris_fit": [
        "Integra\u00e7\u00e3o LLM",
        "RAG / Mem\u00f3ria"
      ],
      "combination_rationale": "",
      "project_names": [],
      "source": "github"
    },
    {
      "id": "gh_1024554267",
      "title": "hermes-agent",
      "name": "NousResearch/hermes-agent",
      "score": 81,
      "grade": "S",
      "url": "https://github.com/NousResearch/hermes-agent",
      "iris_fit": [
        "Integra\u00e7\u00e3o LLM"
      ],
      "combination_rationale": "",
      "project_names": [],
      "source": "github"
    },
    {
      "id": "gh_1119531734",
      "title": "full-stack-ai-agent-template",
      "name": "vstorm-co/full-stack-ai-agent-template",
      "score": 80,
      "grade": "S",
      "url": "https://github.com/vstorm-co/full-stack-ai-agent-template",
      "iris_fit": [
        "Integra\u00e7\u00e3o LLM",
        "Backend API",
        "RAG / Mem\u00f3ria"
      ],
      "combination_rationale": "",
      "project_names": [],
      "source": "github"
    },
    {
      "id": "gh_1175857225",
      "title": "skales",
      "name": "skalesapp/skales",
      "score": 77,
      "grade": "S",
      "url": "https://github.com/skalesapp/skales",
      "iris_fit": [
        "Integra\u00e7\u00e3o LLM",
        "Automa\u00e7\u00e3o de workflows"
      ],
      "combination_rationale": "",
      "project_names": [],
      "source": "github"
    },
    {
      "id": "gh_1154407752",
      "title": "awesome-ai-agent-papers",
      "name": "VoltAgent/awesome-ai-agent-papers",
      "score": 76,
      "grade": "S",
      "url": "https://github.com/VoltAgent/awesome-ai-agent-papers",
      "iris_fit": [
        "Integra\u00e7\u00e3o LLM",
        "RAG / Mem\u00f3ria"
      ],
      "combination_rationale": "",
      "project_names": [],
      "source": "github"
    }
  ]
};
