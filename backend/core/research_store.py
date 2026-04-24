"""
AI Office System — Research Store
Armazena e gerencia findings do agente SCOUT.

Responsabilidades:
  - Persist findings em JSON em .runtime/research_findings.json
  - Gerencia configuração de agendamento (schedule_config.json)
  - Controla o loop de scraping agendado
  - Fornece acesso in-memory para a API
"""
import asyncio
import json
import logging
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_RUNTIME_DIR = Path(".runtime")
_ROOT = Path(__file__).resolve().parents[2]
_FINDINGS_FILE = _RUNTIME_DIR / "research_findings.json"
_CONFIG_FILE = _RUNTIME_DIR / "research_schedule_config.json"
_PROMOTED_INSIGHTS_DIR = _ROOT / "docs" / "research-insights"
_PRODUCT_CATS = {"produto_novo", "ia_generativa_mercado", "combinacoes_estrategicas"}
_IRIS_CATS = {"novos_plugins", "integracao_llm", "memoria_rag", "automacao_workflow"}

_DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": True,
    "github_enabled": True,
    "gitlab_enabled": True,
    "huggingface_enabled": True,
    "interval_hours": 6,
    "scrape_time": "08:00",
    "github_queries": [
        "AI agent orchestration",
        "LLM multi-agent framework",
        "crewai langgraph",
        "autonomous AI workflow",
        "model context protocol MCP",
        "local LLM ollama agent",
        "AI developer tool open source",
        "AI SaaS starter kit",
        "code generation agent",
        "AI coding assistant CLI",
    ],
    "hf_queries": [
        "agent",
        "function calling",
        "instruct",
        "local llm",
        "embedding",
        "code generation",
        "reasoning",
    ],
    "gitlab_queries": [
        "ai agent",
        "llm workflow",
        "rag automation",
        "developer tool ai",
        "mcp agent",
    ],
    "min_stars_github": 50,
    "min_stars_gitlab": 25,
    "days_back": 30,
    "last_run": None,
    "next_run": None,
    "total_runs": 0,
}

# In-memory state
_findings: list[dict[str, Any]] = []
_schedule_config: dict[str, Any] = {}
_is_running: bool = False
_scheduler_task: asyncio.Task | None = None


def _ensure_runtime_dir() -> None:
    _RUNTIME_DIR.mkdir(exist_ok=True)


def _load_findings() -> list[dict[str, Any]]:
    _ensure_runtime_dir()
    if _FINDINGS_FILE.exists():
        try:
            data = json.loads(_FINDINGS_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception as exc:
            logger.warning(f"[ResearchStore] Falha ao carregar findings: {exc}")
    return []


def _save_findings(findings: list[dict[str, Any]]) -> None:
    _ensure_runtime_dir()
    try:
        _FINDINGS_FILE.write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning(f"[ResearchStore] Falha ao salvar findings: {exc}")


def _load_config() -> dict[str, Any]:
    _ensure_runtime_dir()
    if _CONFIG_FILE.exists():
        try:
            data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
            return {**_DEFAULT_CONFIG, **data}
        except Exception as exc:
            logger.warning(f"[ResearchStore] Falha ao carregar config: {exc}")
    return dict(_DEFAULT_CONFIG)


def _save_config(config: dict[str, Any]) -> None:
    _ensure_runtime_dir()
    try:
        _CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning(f"[ResearchStore] Falha ao salvar config: {exc}")


def initialize() -> None:
    """Inicializa o store carregando dados do disco."""
    global _findings, _schedule_config
    _findings = _load_findings()
    _schedule_config = _load_config()
    logger.info(f"[ResearchStore] Inicializado com {len(_findings)} findings.")


def get_findings(
    source: str | None = None,
    min_score: int = 0,
    grade: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Retorna findings filtrados e paginados."""
    items = _findings

    if source:
        items = [f for f in items if f.get("source") == source]
    if min_score > 0:
        items = [f for f in items if f.get("score", 0) >= min_score]
    if grade:
        items = [f for f in items if f.get("grade") == grade]

    total = len(items)
    paginated = items[offset: offset + limit]

    return {
        "total": total,
        "returned": len(paginated),
        "items": paginated,
        "last_updated": _findings[0].get("scraped_at") if _findings else None,
    }


def get_stats() -> dict[str, Any]:
    """Estatísticas dos findings atuais."""
    if not _findings:
        return {"total": 0, "by_source": {}, "by_grade": {}, "avg_score": 0}

    by_source: dict[str, int] = {}
    by_grade: dict[str, int] = {}
    total_score = 0

    for f in _findings:
        src = f.get("source", "unknown")
        by_source[src] = by_source.get(src, 0) + 1
        grd = f.get("grade", "?")
        by_grade[grd] = by_grade.get(grd, 0) + 1
        total_score += f.get("score", 0)

    return {
        "total": len(_findings),
        "by_source": by_source,
        "by_grade": by_grade,
        "avg_score": round(total_score / len(_findings), 1),
        "top_finding": _findings[0] if _findings else None,
    }


def get_config() -> dict[str, Any]:
    return dict(_schedule_config)


def update_config(updates: dict[str, Any]) -> dict[str, Any]:
    """Atualiza e persiste a configuração de agendamento."""
    global _schedule_config
    _schedule_config = {**_schedule_config, **updates}
    _save_config(_schedule_config)
    logger.info(f"[ResearchStore] Configuração atualizada: {list(updates.keys())}")
    return dict(_schedule_config)


def get_scheduler_status() -> dict[str, Any]:
    return {
        "running": _is_running,
        "scheduler_active": _scheduler_task is not None and not _scheduler_task.done(),
        "last_run": _schedule_config.get("last_run"),
        "next_run": _schedule_config.get("next_run"),
        "total_runs": _schedule_config.get("total_runs", 0),
        "interval_hours": _schedule_config.get("interval_hours", 6),
    }


async def run_scrape(emit_event=None) -> dict[str, Any]:
    """
    Executa uma raspagem completa (GitHub + HuggingFace).
    emit_event: callable opcional para emitir eventos no EventBus.
    """
    global _findings, _is_running

    if _is_running:
        return {"status": "already_running", "message": "Raspagem já em andamento"}

    _is_running = True
    started_at = datetime.now(timezone.utc).isoformat()

    try:
        from backend.tools.github_research_tool import search_github_trending, analyze_combination_potential
        from backend.tools.gitlab_research_tool import search_gitlab_projects
        from backend.tools.hf_research_tool import search_hf_models, search_hf_spaces

        config = _schedule_config
        new_findings: list[dict[str, Any]] = []

        if emit_event:
            await emit_event("research_started", {"sources": _enabled_sources(config)})

        # GitHub scraping
        if config.get("github_enabled", True):
            logger.info("[ResearchStore] Iniciando raspagem GitHub...")
            gh_findings = await search_github_trending(
                queries=config.get("github_queries"),
                min_stars=int(config.get("min_stars_github", 50)),
                days_back=int(config.get("days_back", 30)),
            )
            new_findings.extend(gh_findings)
            logger.info(f"[ResearchStore] GitHub: {len(gh_findings)} projetos encontrados.")

            # Análise de combinações
            combos = await analyze_combination_potential(gh_findings)
            new_findings.extend(combos)
            logger.info(f"[ResearchStore] Combinações: {len(combos)} analisadas.")

        # GitLab scraping
        if config.get("gitlab_enabled", True):
            logger.info("[ResearchStore] Iniciando raspagem GitLab...")
            gitlab_findings = await search_gitlab_projects(
                queries=config.get("gitlab_queries"),
                min_stars=int(config.get("min_stars_gitlab", 25)),
                days_back=int(config.get("days_back", 30)),
            )
            new_findings.extend(gitlab_findings)
            logger.info(f"[ResearchStore] GitLab: {len(gitlab_findings)} projetos encontrados.")

        # HuggingFace scraping
        if config.get("huggingface_enabled", True):
            logger.info("[ResearchStore] Iniciando raspagem HuggingFace...")
            hf_models = await search_hf_models(queries=config.get("hf_queries"))
            new_findings.extend(hf_models)

            hf_spaces = await search_hf_spaces(limit=8)
            new_findings.extend(hf_spaces)
            logger.info(f"[ResearchStore] HuggingFace: {len(hf_models)} modelos + {len(hf_spaces)} spaces.")

        # Merge com findings existentes (mantém histórico, atualiza duplicados)
        existing_by_id = {f["id"]: f for f in _findings}
        for finding in new_findings:
            existing_by_id[finding["id"]] = finding
        _findings = sorted(existing_by_id.values(), key=lambda x: x.get("score", 0), reverse=True)
        _save_findings(_findings)

        # Atualiza config de agendamento
        now = datetime.now(timezone.utc).isoformat()
        interval_hours = int(config.get("interval_hours", 6))
        from datetime import timedelta
        next_run_dt = datetime.now(timezone.utc) + timedelta(hours=interval_hours)
        update_config({
            "last_run": now,
            "next_run": next_run_dt.isoformat(),
            "total_runs": int(config.get("total_runs", 0)) + 1,
        })

        if emit_event:
            await emit_event("research_completed", {
                "total_findings": len(_findings),
                "new_findings": len(new_findings),
                "sources": _enabled_sources(config),
            })

        logger.info(f"[ResearchStore] Raspagem concluída: {len(_findings)} findings totais.")
        return {
            "status": "completed",
            "started_at": started_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "new_findings": len(new_findings),
            "total_findings": len(_findings),
        }

    except Exception as exc:
        logger.error(f"[ResearchStore] Falha na raspagem: {exc}", exc_info=True)
        return {"status": "failed", "error": str(exc), "started_at": started_at}
    finally:
        _is_running = False


def _enabled_sources(config: dict[str, Any]) -> list[str]:
    sources: list[str] = []
    if config.get("github_enabled", True):
        sources.append("github")
    if config.get("gitlab_enabled", True):
        sources.append("gitlab")
    if config.get("huggingface_enabled", True):
        sources.append("huggingface")
    return sources


def _score_product_potential(cat_id: str, top_findings: list[dict], count: int) -> dict:
    """Classifica o potencial de produto comercial e velocidade/qualidade para o dept de inteligência."""
    base_scores = {
        "combinacoes_estrategicas": 92,
        "automacao_workflow": 83,
        "integracao_llm": 78,
        "memoria_rag": 74,
        "novos_plugins": 68,
    }
    score = base_scores.get(cat_id, 60)
    if count >= 10:
        score += 8
    elif count >= 5:
        score += 4
    top_grade = top_findings[0].get("grade", "C") if top_findings else "C"
    if top_grade == "S":
        score += 8
    elif top_grade == "A":
        score += 4
    score = min(100, score)

    if score >= 85:
        viability = "altíssimo"
        viability_color = "#f97316"
        viability_icon = "🔥"
    elif score >= 70:
        viability = "alto"
        viability_color = "#fbbf24"
        viability_icon = "⚡"
    else:
        viability = "médio"
        viability_color = "#22c55e"
        viability_icon = "✦"

    speed_impact = {
        "combinacoes_estrategicas": "Redução de 60–80% no tempo de entrega de features complexas — stacks combinados eliminam camadas de integração manual.",
        "automacao_workflow": "Fluxos autônomos substituem etapas repetitivas que hoje consomem horas de trabalho humano — velocidade de operação 5×.",
        "integracao_llm": "Modelos especializados geram código/análise com menor iteração humana — qualidade de saída +40% vs. modelos genéricos.",
        "memoria_rag": "Agentes com memória persistente não repetem erros anteriores e reutilizam soluções validadas — aprendizado contínuo sem retrabalho.",
        "novos_plugins": "Capacidades novas disponíveis imediatamente para todos os agentes via MCP — sem refatoração de core, plug-and-play.",
    }

    pitches = {
        "combinacoes_estrategicas": (
            "Stack AI completo pronto para white-label. Combina orquestração + LLM + memória numa solução "
            "enterprise vendável como SaaS de automação cognitiva. Mercado-alvo: operações, RH, jurídico, financeiro. "
            "Modelo: assinatura mensal por equipe ($500–2000/mês). Payback estimado: 3–6 meses."
        ),
        "automacao_workflow": (
            "Plataforma de automação no-code/low-code para times de operações e marketing. "
            "Modelo freemium com upsell enterprise. Mercado global de workflow automation: $26B até 2027. "
            "Diferencial: agentes AI nativos — não apenas triggers simples."
        ),
        "integracao_llm": (
            "LLM-as-a-Service com fine-tuning por nicho (jurídico, saúde, finanças, e-commerce). "
            "Pricing por token com camada de segurança e compliance incluída. "
            "Margem bruta alta (70%+). Barreira de entrada: curadoria de dados + expertise de deploy."
        ),
        "memoria_rag": (
            "Knowledge Base inteligente como SaaS — empresas pagam para ter documentos, histórico e "
            "processos acessíveis por agentes AI em tempo real. Recorrência mensal garantida. "
            "Upsell: analytics de uso + relatórios automáticos de inteligência organizacional."
        ),
        "novos_plugins": (
            "Marketplace de ferramentas AI — plugins pay-per-use para agentes autônomos. "
            "Modelo AppStore com 30% de comissão por transação ou assinatura de plugin premium. "
            "Efeito de rede: quanto mais plugins, mais valioso o ecossistema IRIS."
        ),
    }

    return {
        "score": score,
        "viability": viability,
        "viability_color": viability_color,
        "viability_icon": viability_icon,
        "viability_label": f"{viability_icon} Potencial {viability.capitalize()}",
        "speed_impact": speed_impact.get(cat_id, "Impacto direto na velocidade e qualidade do departamento de inteligência."),
        "pitch": pitches.get(cat_id, "Alto potencial de integração comercial como serviço gerenciado de AI."),
    }


def _generate_summary(cat_id: str, top_findings: list[dict], count: int) -> dict[str, str]:
    """Gera um resumo humano do insight: o que é, pra que serve, onde usar, o que implementar."""
    top = top_findings[0] if top_findings else {}
    top_title = top.get("title", "projeto")
    top_names = ", ".join(f.get("title", "") for f in top_findings[:3])

    summaries: dict[str, dict[str, str]] = {
        "novos_plugins": {
            "o_que_e": (
                f"São ferramentas e frameworks de agentes de IA — como {top_names} — que podem ser "
                "integrados ao IRIS como novas capacidades via MCP (Model Context Protocol). "
                "Cada ferramenta vira um 'poder extra' que qualquer agente pode invocar."
            ),
            "para_que_serve": (
                "Serve para expandir o que os agentes IRIS conseguem fazer além do que já fazem hoje: "
                "buscar dados em tempo real, executar código, chamar APIs externas, orquestrar sub-agentes, "
                "e resolver tarefas que atualmente precisam de intervenção humana."
            ),
            "onde_usariamos": (
                f"No PicoClaw MCP Bridge (gateway central de ferramentas do IRIS). "
                f"O agente Dev, o Marketing e o SCOUT passariam a ter acesso às ferramentas de '{top_title}' "
                "como funções nativas, chamadas diretamente durante a execução de tarefas."
            ),
            "o_que_implementariamos": (
                f"Uma classe Tool wrapper para '{top_title}' registrada no backend IRIS. "
                "Com isso: qualquer agente pode invocar a ferramenta via `tool.run(input)`, "
                "o resultado aparece no log de execução, e a tarefa avança automaticamente — "
                "sem precisar de um humano para fazer essa etapa manual."
            ),
        },
        "integracao_llm": {
            "o_que_e": (
                f"São modelos de linguagem e integrações com provedores de IA — como {top_names}. "
                "Incluem LLMs locais (rodando no seu Ollama) e modelos cloud (via OpenRouter), "
                "cada um com diferentes perfis de velocidade, custo e qualidade."
            ),
            "para_que_serve": (
                "Serve para melhorar a qualidade das respostas dos agentes IRIS ou reduzir custo/latência. "
                "Diferentes tarefas precisam de diferentes modelos: código exige precisão, "
                "marketing exige criatividade, análise exige raciocínio longo."
            ),
            "onde_usariamos": (
                "No `brain_router.py` — o roteador central de modelos do IRIS. "
                "Cada perfil de agente (dev, marketing, scout, qa) pode apontar para o modelo mais adequado. "
                "Um novo modelo pode ser adicionado como opção local no Ollama ou cloud no OpenRouter."
            ),
            "o_que_implementariamos": (
                f"Adicionar '{top_title}' como novo modelo disponível no brain_router, "
                "criar um perfil de agente específico (ex: 'coder_v2') apontando para ele, "
                "e validar com um smoke test de geração de código e raciocínio. "
                "Resultado: agentes mais inteligentes para tarefas específicas, sem custo extra."
            ),
        },
        "memoria_rag": {
            "o_que_e": (
                f"São sistemas de embeddings e recuperação semântica — como {top_names}. "
                "Transformam textos em vetores numéricos para encontrar informações relevantes "
                "por similaridade de significado, não apenas por palavra-chave."
            ),
            "para_que_serve": (
                "Serve para dar memória de longo prazo aos agentes IRIS: lembrar de projetos anteriores, "
                "decisões técnicas já tomadas, padrões de código do repositório, e contexto de tarefas passadas. "
                "Hoje os agentes 'esquecem tudo' a cada nova sessão — RAG resolve isso."
            ),
            "onde_usariamos": (
                "No memory-gateway e no Supabase (que já está configurado no IRIS). "
                "Antes de executar uma tarefa, o agente consultaria o RAG: "
                "'já fizemos algo parecido antes?' — e reutilizaria soluções anteriores "
                "em vez de reinventar do zero."
            ),
            "o_que_implementariamos": (
                f"Pipeline RAG com '{top_title}': ao concluir cada tarefa, salvar o resumo + "
                "código gerado como vetores no Supabase. Ao iniciar nova tarefa, recuperar "
                "os 3 contextos mais similares e incluir no prompt do agente. "
                "Resultado prático: agentes que aprendem com o histórico do projeto."
            ),
        },
        "automacao_workflow": {
            "o_que_e": (
                f"São ferramentas de orquestração de fluxos — como {top_names}. "
                "Permitem definir sequências de etapas, condições, loops e paralelismo "
                "entre diferentes sistemas e serviços de forma visual ou declarativa."
            ),
            "para_que_serve": (
                "Serve para automatizar tarefas repetitivas que hoje precisam de cliques manuais: "
                "deploy após aprovação, geração de relatório toda segunda, disparo de campanha "
                "ao atingir um gatilho — tudo acontecendo sozinho, sem intervenção humana."
            ),
            "onde_usariamos": (
                "Como triggers no scheduler do IRIS (já existe o research_scheduler) e como "
                "novos nós no LangGraph dos orquestradores. "
                "Ex: workflow 'feature completa → testes → deploy → notifica Slack' "
                "rodando automaticamente ao aprovar uma task."
            ),
            "o_que_implementariamos": (
                f"Integrar '{top_title}' como motor de workflow externo ou como novo padrão "
                "de nós no LangGraph. Criar o primeiro workflow end-to-end: "
                "Dev conclui task → Marketing gera copy → post agendado → relatório enviado. "
                "Tudo automático, rastreável no Command Center."
            ),
        },
        "combinacoes_estrategicas": {
            "o_que_e": (
                f"São pares de projetos complementares identificados pelo SCOUT-01 — como '{top_title}'. "
                "Cada combinação une duas tecnologias que, juntas, formam um stack mais poderoso "
                "do que cada uma separada, cobrindo lacunas uma da outra."
            ),
            "para_que_serve": (
                "Serve para criar capacidades compostas no IRIS: "
                "um framework de agentes + um provedor LLM = agentes autônomos completos. "
                "Ou: sistema de memória + orquestrador = agentes que aprendem e lembram. "
                "É a diferença entre ter peças e ter um produto funcionando."
            ),
            "onde_usariamos": (
                "Como foundation para novos módulos do IRIS. "
                f"A combinação '{top_title}' poderia virar um novo time de agentes especializado, "
                "ou substituir uma parte do stack atual com uma solução mais moderna e integrada. "
                "Alta alavancagem: duas integrações pelo preço do esforço de uma."
            ),
            "o_que_implementariamos": (
                "Implementação sequencial: primeiro o projeto A (MVP funcional), "
                "depois integração com projeto B aproveitando a interface já criada. "
                "Criar um novo orchestrator ou tool que usa os dois juntos, "
                "com fallback para o stack atual caso algo falhe — zero risco de regressão."
            ),
        },
        "produto_novo": {
            "o_que_e": (
                f"São oportunidades de mercado identificadas a partir de projetos como '{top_title}'. "
                f"O SCOUT mapeou {count} ferramentas/plataformas que indicam uma lacuna comercial "
                "que podemos explorar construindo um produto novo — não apenas uma integração ao IRIS."
            ),
            "para_que_serve": (
                "Serve para identificar onde o mercado ainda não tem uma solução consolidada "
                "e onde o IRIS pode ser a base de um produto lançável ao público. "
                "Diferente dos outros insights, aqui o objetivo é criar algo novo para vender ou open-sourcear."
            ),
            "onde_usariamos": (
                "Como ponto de partida para um novo repositório público no GitHub. "
                "O Time DEV cria o MVP, o Time MARKETING define o posicionamento e UVP, "
                "e o produto é publicado como ferramenta standalone — não só um módulo do IRIS."
            ),
            "o_que_implementariamos": (
                f"MVP do produto inspirado em '{top_title}': "
                "estrutura de repositório, README completo com proposta de valor, "
                "landing page estática, e primeira versão funcional do core do produto. "
                "Resultado: repo público no GitHub pronto para estrelas e contribuidores."
            ),
        },
        "ia_generativa_mercado": {
            "o_que_e": (
                f"'{top_title}' e outros {count - 1} modelos/frameworks de alto grau (S/A) "
                "que representam o estado da arte atual em IA generativa. "
                "São os que a comunidade está adotando agora e que definirão o padrão dos próximos 6-12 meses."
            ),
            "para_que_serve": (
                "Serve para manter o IRIS na vanguarda técnica e identificar quais modelos "
                "podemos usar agora para aumentar a qualidade das entregas dos agentes. "
                "Também aponta tendências que podem virar produtos comerciais antes da concorrência."
            ),
            "onde_usariamos": (
                "Como novos modelos no BrainRouter — substituindo ou complementando os modelos atuais. "
                "Também como base para demonstrações públicas do IRIS "
                "usando os modelos mais modernos disponíveis, aumentando credibilidade da plataforma."
            ),
            "o_que_implementariamos": (
                f"Integrar '{top_title}' ao BrainRouter como candidato para roles específicos (raciocínio, código, análise). "
                "Criar um benchmark comparativo entre o modelo atual e o novo — "
                "medindo qualidade de output e tempo de resposta. "
                "Publicar os resultados como conteúdo técnico no GitHub."
            ),
        },
    }

    default = {
        "o_que_e": f"{count} projetos identificados pelo SCOUT-01 com potencial de integração ao IRIS.",
        "para_que_serve": "Expandir as capacidades do sistema com tecnologias validadas pela comunidade open-source.",
        "onde_usariamos": "No backend IRIS, como novas ferramentas ou módulos de suporte aos agentes.",
        "o_que_implementariamos": f"Avaliar '{top_title}' em profundidade e criar uma prova de conceito integrada.",
    }
    return summaries.get(cat_id, default)


def _generate_recommendation(cat_id: str, findings: list[dict], count: int) -> str:
    if not findings:
        return ""
    top = findings[0]
    top_title = top.get("title", "projeto")
    recs = {
        "novos_plugins": f"Integrar '{top_title}' como ferramenta MCP dos agentes IRIS — {count} projetos com potencial de expansão de capacidades.",
        "integracao_llm": f"Avaliar '{top_title}' como LLM alternativo/complementar para os agentes IRIS — {count} modelos identificados.",
        "memoria_rag": f"Implementar '{top_title}' para memória persistente entre sessões dos agentes — {count} soluções de RAG encontradas.",
        "automacao_workflow": f"Usar '{top_title}' para pipelines automáticos entre agentes Dev e Marketing — {count} ferramentas de automação disponíveis.",
        "combinacoes_estrategicas": f"'{top.get('title', '')}': {top.get('combination_rationale', 'combinação de alto impacto para o stack IRIS')}",
        "produto_novo": f"Criar um produto standalone inspirado em '{top_title}' — {count} oportunidades de mercado mapeadas com lacuna identificada.",
        "ia_generativa_mercado": f"'{top_title}' representa o estado da arte — {count} modelos/frameworks de alto grau com potencial comercial imediato.",
    }
    return recs.get(cat_id, f"{count} projetos encontrados com potencial de integração no IRIS.")


def generate_insights() -> dict[str, Any]:
    """Analisa findings e gera insights de melhoria categorizados para o IRIS."""
    if not _findings:
        return {"insights": [], "total_analyzed": 0, "generated_at": datetime.now(timezone.utc).isoformat()}

    categories: dict[str, dict[str, Any]] = {
        "novos_plugins": {
            "title": "Novos Plugins para Agentes",
            "description": "Ferramentas integráveis via MCP que expandem as capacidades dos agentes IRIS",
            "color": "#38bdf8",
            "icon": "🔌",
            "keywords": {"agent", "agents", "orchestration", "mcp", "model-context-protocol", "tool", "plugin"},
            "iris_fit_match": {"Orquestração de agentes", "MCP / Ferramentas"},
            "findings": [],
        },
        "integracao_llm": {
            "title": "Aprimoramento de LLM",
            "description": "Modelos e integrações que melhoram as capacidades de linguagem dos agentes",
            "color": "#22c55e",
            "icon": "🧠",
            "keywords": {"llm", "ollama", "openai", "claude", "anthropic", "instruct", "function-calling", "text-generation"},
            "iris_fit_match": {"Integração LLM", "LLM / Geração de texto", "Agentes / Tool Use"},
            "findings": [],
        },
        "memoria_rag": {
            "title": "Memória e RAG",
            "description": "Sistemas de recuperação e persistência de contexto para agentes",
            "color": "#a78bfa",
            "icon": "💾",
            "keywords": {"rag", "embeddings", "vector-db", "memory", "retrieval", "chroma", "faiss", "pgvector"},
            "iris_fit_match": {"RAG / Memória", "Embeddings / RAG", "Modelos locais (Ollama)"},
            "findings": [],
        },
        "automacao_workflow": {
            "title": "Automação de Workflows",
            "description": "Ferramentas para automatizar fluxos entre agentes e sistemas externos",
            "color": "#f97316",
            "icon": "⚙️",
            "keywords": {"workflow", "automation", "pipeline", "n8n", "langgraph", "airflow", "prefect"},
            "iris_fit_match": {"Automação de workflows", "Backend API"},
            "findings": [],
        },
        "combinacoes_estrategicas": {
            "title": "Combinações Estratégicas",
            "description": "Projetos que, integrados, criam capacidades únicas e de alto impacto para o IRIS",
            "color": "#fbbf24",
            "icon": "⚡",
            "keywords": set(),
            "iris_fit_match": set(),
            "findings": [],
        },
        "produto_novo": {
            "title": "Oportunidade de Novo Produto",
            "description": "Tendências de mercado que indicam lacunas onde o IRIS ou um novo produto pode ser lançado",
            "color": "#f43f5e",
            "icon": "🚀",
            "keywords": {"saas", "platform", "dashboard", "marketplace", "cli", "sdk", "api", "app", "startup", "developer-tool", "developer-experience", "devtool", "productivity"},
            "iris_fit_match": {"Ferramentas para Devs", "Produtividade", "Automação", "Developer Experience"},
            "findings": [],
        },
        "ia_generativa_mercado": {
            "title": "IA Generativa — Tendência de Mercado",
            "description": "Modelos e sistemas de alto grau que definem o estado da arte e oportunidades comerciais em IA generativa",
            "color": "#ec4899",
            "icon": "✦",
            "keywords": {"generative", "gpt", "llama", "mistral", "gemma", "phi", "qwen", "deepseek", "reasoning", "code", "multimodal", "vision"},
            "iris_fit_match": {"Geração de código", "Raciocínio", "Multimodal", "Estado da Arte"},
            "findings": [],
        },
    }

    for finding in _findings:
        if finding.get("type") == "combination" or finding.get("source") == "combination":
            categories["combinacoes_estrategicas"]["findings"].append(finding)
            continue

        topics = set(finding.get("topics", []))
        iris_fit = set(finding.get("iris_fit", []))
        score = finding.get("score", 0)

        iris_matched = False
        product_matched = False

        # Try IRIS-improvement categories first
        for cat_id in _IRIS_CATS:
            cat = categories[cat_id]
            if topics & cat["keywords"] or iris_fit & cat["iris_fit_match"]:
                cat["findings"].append(finding)
                iris_matched = True
                break

        # Also check product/market categories independently (a finding can serve both)
        for cat_id in ("produto_novo", "ia_generativa_mercado"):
            cat = categories[cat_id]
            if topics & cat["keywords"] or iris_fit & cat["iris_fit_match"]:
                cat["findings"].append(finding)
                product_matched = True
                break

        # High-grade findings without a match still feed product discovery
        if not iris_matched and not product_matched and score >= 60:
            categories["ia_generativa_mercado"]["findings"].append(finding)
        elif not iris_matched and score >= 40:
            categories["novos_plugins"]["findings"].append(finding)

    insights = []
    for cat_id, cat in categories.items():
        sorted_findings = sorted(cat["findings"], key=lambda x: x.get("score", 0), reverse=True)
        top5 = sorted_findings[:5]
        if not top5:
            continue

        insights.append({
            "category_id": cat_id,
            "title": cat["title"],
            "description": cat["description"],
            "color": cat["color"],
            "icon": cat["icon"],
            "total_found": len(cat["findings"]),
            "delivery_mode": classify_insight_delivery(cat_id),
            "recommendation": _generate_recommendation(cat_id, top5, len(cat["findings"])),
            "summary": _generate_summary(cat_id, top5, len(cat["findings"])),
            "product_potential": _score_product_potential(cat_id, top5, len(cat["findings"])),
            "top_projects": [
                {
                    "id": f.get("id", ""),
                    "title": f.get("title", ""),
                    "name": f.get("name", ""),
                    "score": f.get("score", 0),
                    "grade": f.get("grade", ""),
                    "url": f.get("url", ""),
                    "iris_fit": f.get("iris_fit", []),
                    "combination_rationale": f.get("combination_rationale", ""),
                    "project_names": f.get("project_names", []),
                    "source": f.get("source", ""),
                }
                for f in top5
            ],
        })

    insights.sort(key=lambda x: x["total_found"], reverse=True)

    return {
        "insights": insights,
        "total_analyzed": len(_findings),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def classify_insight_delivery(category_id: str) -> dict[str, str]:
    category = (category_id or "").strip().lower()
    if category in _PRODUCT_CATS:
        return {
            "project_kind": "standalone_product",
            "repo_strategy": "dedicated_repository",
            "commit_scope": "exclusive",
        }
    if category in _IRIS_CATS:
        return {
            "project_kind": "iris_improvement",
            "repo_strategy": "iris_repository",
            "commit_scope": "platform",
        }
    return {
        "project_kind": "unknown",
        "repo_strategy": "iris_repository",
        "commit_scope": "platform",
    }


def promote_insight(category_id: str) -> dict[str, Any]:
    """Create and commit an implementation brief for one generated insight."""
    payload = generate_insights()
    insight = next(
        (item for item in payload.get("insights", []) if item.get("category_id") == category_id),
        None,
    )
    if not insight:
        raise KeyError(category_id)

    _PROMOTED_INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    slug = _slugify(f"{category_id}-{insight.get('title', 'insight')}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    relative_path = Path("docs") / "research-insights" / f"{stamp}-{slug}.md"
    target = _ROOT / relative_path
    target.write_text(_build_promoted_insight_markdown(insight, payload), encoding="utf-8")

    commit_message = f"SCOUT: promote {category_id} insight"
    commit_sha = _commit_file(relative_path, commit_message)
    return {
        "status": "promoted",
        "category_id": category_id,
        "path": str(target),
        "repo_relative_path": str(relative_path).replace("\\", "/"),
        "commit_message": commit_message,
        "commit_sha": commit_sha,
    }


def _build_promoted_insight_markdown(insight: dict[str, Any], payload: dict[str, Any]) -> str:
    top_projects = insight.get("top_projects") or []
    summary = insight.get("summary") or {}
    potential = insight.get("product_potential") or {}
    project_lines = "\n".join(
        f"{idx}. [{project.get('title') or project.get('name')}]({project.get('url') or '#'}) "
        f"- grade {project.get('grade')} / score {project.get('score')} / source {project.get('source')}"
        for idx, project in enumerate(top_projects, start=1)
    )

    return f"""# SCOUT Insight Promotion - {insight.get('title')}

Generated at: {datetime.now(timezone.utc).isoformat()}

## Category

- ID: `{insight.get('category_id')}`
- Total found: {insight.get('total_found')}
- Total analyzed by SCOUT: {payload.get('total_analyzed')}
- Recommendation: {insight.get('recommendation')}

## Market Potential

- Score: {potential.get('score', 'n/a')}
- Viability: {potential.get('viability', 'n/a')}
- Speed/quality impact: {potential.get('speed_impact', 'n/a')}

{potential.get('pitch', '')}

## Implementation Summary

### What It Is

{summary.get('o_que_e', '')}

### Why It Matters

{summary.get('para_que_serve', '')}

### Where IRIS Uses It

{summary.get('onde_usariamos', '')}

### What We Build

{summary.get('o_que_implementariamos', '')}

## Top Projects

{project_lines or '- No projects available.'}

## Delivery Contract

- Create a technical spike before production integration.
- Keep implementation inside the authorized IRIS workspace or AIteams project root.
- Commit every new artifact with `github_commit`.
- Return `DELIVERY_EVIDENCE` with validation and SHA.
- Block promotion if license, security, or dependency risk is unacceptable.
"""


def _commit_file(relative_path: Path, commit_message: str) -> str:
    subprocess.run(["git", "add", "--", str(relative_path)], cwd=_ROOT, check=True, timeout=10)
    result = subprocess.run(
        ["git", "commit", "-m", commit_message],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=20,
    )
    if result.returncode != 0:
        combined = (result.stdout + "\n" + result.stderr).strip()
        if "nothing to commit" not in combined.lower():
            raise RuntimeError(combined or "git commit failed")
    sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
        timeout=10,
    ).stdout.strip()
    return sha


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:72] or "insight"


async def _scheduler_loop() -> None:
    """Loop de agendamento que executa scraping conforme configurado."""
    logger.info("[ResearchScheduler] Loop de agendamento iniciado.")
    while True:
        try:
            config = _schedule_config
            if not config.get("enabled", True):
                await asyncio.sleep(60)
                continue

            interval_hours = int(config.get("interval_hours", 6))
            await asyncio.sleep(interval_hours * 3600)

            if config.get("enabled", True):
                logger.info("[ResearchScheduler] Executando scraping agendado...")
                await run_scrape()
        except asyncio.CancelledError:
            logger.info("[ResearchScheduler] Loop de agendamento cancelado.")
            break
        except Exception as exc:
            logger.warning(f"[ResearchScheduler] Erro no loop: {exc}")
            await asyncio.sleep(300)


def start_scheduler() -> None:
    """Inicia o loop de agendamento como background task."""
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_scheduler_loop())
        logger.info("[ResearchScheduler] Scheduler iniciado.")


def stop_scheduler() -> None:
    """Para o loop de agendamento."""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        logger.info("[ResearchScheduler] Scheduler parado.")
