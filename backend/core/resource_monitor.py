"""
Resource Monitor — determina capacidade real da máquina.
Consultado pelo orquestrador antes de criar agentes.
Garante que não sobrecarregamos a máquina local.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx
import psutil

logger = logging.getLogger(__name__)

# Importação condicional de pynvml (GPU NVIDIA) — sem crash se ausente
try:
    import pynvml  # type: ignore

    pynvml.nvmlInit()
    _PYNVML_AVAILABLE = True
except Exception:
    _PYNVML_AVAILABLE = False
    logger.info("[ResourceMonitor] pynvml não disponível — métricas de GPU desabilitadas.")

_OLLAMA_BASE_URL = "http://127.0.0.1:11434"

# Papéis dev (favorecidos por modelos de código)
_CODE_ROLES = {"planner", "frontend", "backend", "qa", "security", "docs"}
# Papéis marketing
_GENERAL_ROLES = {"research", "strategy", "content", "seo", "social", "analytics", "orchestrator"}


class ResourceMonitor:
    """
    Coleta métricas de RAM, CPU, GPU e Ollama em tempo real.
    Todas as funções públicas são métodos de instância E também expostas
    como funções de módulo para uso conveniente.
    """

    # ------------------------------------------------------------------
    # Coleta de recursos
    # ------------------------------------------------------------------

    async def get_system_resources(self) -> dict:
        """
        Retorna snapshot completo dos recursos da máquina.

        Formato:
        {
            "ram_total_gb":      float,
            "ram_available_gb":  float,
            "ram_used_pct":      float,
            "cpu_count":         int,
            "cpu_usage_pct":     float,
            "gpu_available":     bool,
            "gpu_vram_total_gb": float,  # 0.0 se sem GPU
            "gpu_vram_free_gb":  float,
            "ollama_online":     bool,
            "ollama_models":     list[str],
        }
        """
        # --- RAM ---
        mem = psutil.virtual_memory()
        ram_total_gb = round(mem.total / 1024**3, 2)
        ram_available_gb = round(mem.available / 1024**3, 2)
        ram_used_pct = round(mem.percent, 1)

        # --- CPU ---
        cpu_count = psutil.cpu_count(logical=True) or 1
        # interval=0.5 evita leitura zerada na primeira chamada
        cpu_usage_pct = round(psutil.cpu_percent(interval=0.5), 1)

        # --- GPU ---
        gpu_available = False
        gpu_vram_total_gb = 0.0
        gpu_vram_free_gb = 0.0

        if _PYNVML_AVAILABLE:
            try:
                device_count = pynvml.nvmlDeviceGetCount()
                if device_count > 0:
                    # Agrega todas as GPUs disponíveis
                    total_vram = 0
                    free_vram = 0
                    for i in range(device_count):
                        handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                        total_vram += mem_info.total
                        free_vram += mem_info.free
                    gpu_available = True
                    gpu_vram_total_gb = round(total_vram / 1024**3, 2)
                    gpu_vram_free_gb = round(free_vram / 1024**3, 2)
            except Exception as exc:
                logger.warning("[ResourceMonitor] Erro ao consultar GPU via pynvml: %s", exc)

        # --- Ollama ---
        ollama_online, ollama_models = await self._check_ollama()

        return {
            "ram_total_gb": ram_total_gb,
            "ram_available_gb": ram_available_gb,
            "ram_used_pct": ram_used_pct,
            "cpu_count": cpu_count,
            "cpu_usage_pct": cpu_usage_pct,
            "gpu_available": gpu_available,
            "gpu_vram_total_gb": gpu_vram_total_gb,
            "gpu_vram_free_gb": gpu_vram_free_gb,
            "ollama_online": ollama_online,
            "ollama_models": ollama_models,
        }

    # ------------------------------------------------------------------
    # Cálculo de capacidade
    # ------------------------------------------------------------------

    def calculate_max_agents(self, resources: dict) -> int:
        """
        Regras:
          Base    : 1 agente por 4 GB de RAM disponível
          GPU     : +2 agentes por 8 GB de VRAM livre
          CPU > 80%: reduz em 50% (arredondado para cima)
          Limites : mínimo 2, máximo 12

        Retorna: int
        """
        ram_available_gb: float = resources.get("ram_available_gb", 0.0)
        cpu_usage_pct: float = resources.get("cpu_usage_pct", 0.0)
        gpu_available: bool = resources.get("gpu_available", False)
        gpu_vram_free_gb: float = resources.get("gpu_vram_free_gb", 0.0)

        # Base: 1 agente por 4 GB RAM disponível
        base = int(ram_available_gb / 4)

        # Bonus GPU: +2 por cada 8 GB de VRAM livre
        gpu_bonus = 0
        if gpu_available and gpu_vram_free_gb > 0:
            gpu_bonus = int(gpu_vram_free_gb / 8) * 2

        total = base + gpu_bonus

        # CPU muito ocupada → reduz pela metade (arredonda para cima)
        if cpu_usage_pct > 80.0:
            import math
            total = math.ceil(total / 2)

        # Aplicar limites absolutos
        total = max(2, min(12, total))
        return total

    def get_recommended_model_for_resources(self, resources: dict, role: str) -> str:
        """
        Seleciona o modelo Ollama mais adequado dado os recursos disponíveis.

        Hierarquia por RAM disponível:
          > 24 GB  → qwen2.5-coder:32b  (roles de código) / llama3.1:8b (marketing)
          8–24 GB  → qwen3-vl:8b
          < 8 GB   → iris-fast:latest ou llama3.2:3b
        """
        ram_available_gb: float = resources.get("ram_available_gb", 0.0)
        role_lower = role.lower()

        if ram_available_gb > 24.0:
            if role_lower in _CODE_ROLES:
                return "qwen2.5-coder:32b"
            return "llama3.1:8b"

        if ram_available_gb >= 8.0:
            return "qwen3-vl:8b"

        # Pouca RAM disponível — usar modelo leve
        ollama_models: list[str] = resources.get("ollama_models", [])
        if "iris-fast:latest" in ollama_models:
            return "iris-fast:latest"
        return "llama3.2:3b"

    async def get_capacity_report(self) -> dict:
        """
        Relatório completo para o orquestrador usar antes de criar agentes.

        Formato:
        {
            "resources":              dict,       # snapshot de get_system_resources()
            "max_agents":             int,        # cálculo de calculate_max_agents()
            "recommended_models_by_role": dict,   # role → model_id
            "bottleneck":             str,        # "ram" | "cpu" | "gpu" | "none"
        }
        """
        resources = await self.get_system_resources()
        max_agents = self.calculate_max_agents(resources)

        all_roles = list(_CODE_ROLES | _GENERAL_ROLES)
        recommended_models_by_role = {
            role: self.get_recommended_model_for_resources(resources, role)
            for role in all_roles
        }

        bottleneck = self._identify_bottleneck(resources)

        logger.info(
            "[ResourceMonitor] Capacidade: %d agentes | RAM=%.1f GB disp. | "
            "CPU=%.1f%% | GPU=%s | Gargalo=%s",
            max_agents,
            resources["ram_available_gb"],
            resources["cpu_usage_pct"],
            resources["gpu_available"],
            bottleneck,
        )

        return {
            "resources": resources,
            "max_agents": max_agents,
            "recommended_models_by_role": recommended_models_by_role,
            "bottleneck": bottleneck,
        }

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------

    async def _check_ollama(self) -> tuple[bool, list[str]]:
        """Verifica Ollama e retorna (online, lista_de_modelos)."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{_OLLAMA_BASE_URL}/api/tags")
                if resp.status_code == 200:
                    raw_models = resp.json().get("models", [])
                    model_names = [m["name"] for m in raw_models]
                    return True, model_names
        except Exception as exc:
            logger.warning("[ResourceMonitor] Ollama offline: %s", exc)
        return False, []

    def _identify_bottleneck(self, resources: dict) -> str:
        """
        Identifica o principal gargalo de recursos.
        Retorna: "ram" | "cpu" | "gpu" | "none"
        """
        ram_used_pct: float = resources.get("ram_used_pct", 0.0)
        cpu_usage_pct: float = resources.get("cpu_usage_pct", 0.0)
        gpu_available: bool = resources.get("gpu_available", False)
        gpu_vram_total_gb: float = resources.get("gpu_vram_total_gb", 0.0)
        gpu_vram_free_gb: float = resources.get("gpu_vram_free_gb", 0.0)

        if ram_used_pct > 85.0:
            return "ram"
        if cpu_usage_pct > 80.0:
            return "cpu"
        if gpu_available and gpu_vram_total_gb > 0:
            gpu_used_pct = ((gpu_vram_total_gb - gpu_vram_free_gb) / gpu_vram_total_gb) * 100
            if gpu_used_pct > 85.0:
                return "gpu"
        return "none"


# ---------------------------------------------------------------------------
# Singleton de módulo — instância padrão para uso direto
# ---------------------------------------------------------------------------

_monitor = ResourceMonitor()


async def get_system_resources() -> dict:
    """Atalho de módulo para ResourceMonitor().get_system_resources()."""
    return await _monitor.get_system_resources()


def calculate_max_agents(resources: dict) -> int:
    """Atalho de módulo para ResourceMonitor().calculate_max_agents()."""
    return _monitor.calculate_max_agents(resources)


def get_recommended_model_for_resources(resources: dict, role: str) -> str:
    """Atalho de módulo para ResourceMonitor().get_recommended_model_for_resources()."""
    return _monitor.get_recommended_model_for_resources(resources, role)


async def get_capacity_report() -> dict:
    """Atalho de módulo para ResourceMonitor().get_capacity_report()."""
    return await _monitor.get_capacity_report()
