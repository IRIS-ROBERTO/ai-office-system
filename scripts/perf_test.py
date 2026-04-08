"""
IRIS — Performance & Integration Test Suite
==========================================
Testa todos os endpoints da API, mede latências, e executa tasks reais
em ambos os times (Dev + Marketing) com monitoramento em tempo real.

Uso:
    python scripts/perf_test.py [--base-url http://localhost:8000]
"""
import asyncio
import json
import sys
import time
import statistics
from dataclasses import dataclass, field
from typing import Optional
import httpx
import websockets

BASE_URL = "http://localhost:8000"
WS_URL  = "ws://localhost:8000/ws"

# ─── Cores ANSI ──────────────────────────────────────────────────────────────
G  = "\033[92m"  # verde
Y  = "\033[93m"  # amarelo
R  = "\033[91m"  # vermelho
B  = "\033[94m"  # azul
C  = "\033[96m"  # ciano
M  = "\033[95m"  # magenta
W  = "\033[97m"  # branco
DIM = "\033[2m"
RST = "\033[0m"
BOLD = "\033[1m"

def ok(msg):   print(f"  {G}[OK]{RST}  {msg}")
def err(msg):  print(f"  {R}[ERR]{RST} {msg}")
def info(msg): print(f"  {B}[--]{RST}  {msg}")
def warn(msg): print(f"  {Y}[!!]{RST}  {msg}")
def hdr(msg):  print(f"\n{BOLD}{C}{'='*60}{RST}\n{BOLD}{W}  {msg}{RST}\n{C}{'='*60}{RST}")
def sub(msg):  print(f"\n  {M}>> {msg}{RST}")

@dataclass
class PerfResult:
    name: str
    latencies_ms: list[float] = field(default_factory=list)
    errors: int = 0
    successes: int = 0

    def record(self, lat: float, success: bool):
        self.latencies_ms.append(lat)
        if success:
            self.successes += 1
        else:
            self.errors += 1

    def report(self):
        if not self.latencies_ms:
            warn(f"{self.name}: sem dados")
            return
        avg = statistics.mean(self.latencies_ms)
        p95 = sorted(self.latencies_ms)[int(len(self.latencies_ms)*0.95)]
        mn  = min(self.latencies_ms)
        mx  = max(self.latencies_ms)
        color = G if avg < 200 else Y if avg < 1000 else R
        print(f"    {W}{self.name}{RST}")
        print(f"      avg={color}{avg:.0f}ms{RST}  min={G}{mn:.0f}ms{RST}  "
              f"max={Y}{mx:.0f}ms{RST}  p95={C}{p95:.0f}ms{RST}  "
              f"ok={G}{self.successes}{RST}  err={R}{self.errors}{RST}")

# ─── Test 1: Health ──────────────────────────────────────────────────────────
async def test_health(client: httpx.AsyncClient) -> dict:
    sub("Health Check — /health")
    t = time.perf_counter()
    try:
        r = await client.get(f"{BASE_URL}/health", timeout=10)
        lat = (time.perf_counter() - t) * 1000
        data = r.json()
        ok(f"Status {r.status_code} em {lat:.0f}ms")
        print(f"    api={G}{data.get('api','?')}{RST}  "
              f"redis={C}{data.get('redis','?')}{RST}  "
              f"ollama={M}{data.get('ollama','?')}{RST}")
        models = data.get("available_models", [])
        if models:
            ok(f"Ollama modelos ({len(models)}): {', '.join(m['name'] if isinstance(m,dict) else m for m in models[:4])}...")
        else:
            warn("Ollama offline — agentes usarao OpenRouter/Gemini como fallback")
        return data
    except Exception as e:
        err(f"Health check falhou: {e}")
        return {}

# ─── Test 2: Endpoint Stress ─────────────────────────────────────────────────
async def test_endpoint_stress(client: httpx.AsyncClient, n: int = 20) -> PerfResult:
    sub(f"Stress GET /health  ({n}x concorrente)")
    result = PerfResult("GET /health stress")
    tasks = []
    async def call():
        t = time.perf_counter()
        try:
            r = await client.get(f"{BASE_URL}/health", timeout=5)
            result.record((time.perf_counter() - t)*1000, r.status_code == 200)
        except Exception:
            result.record((time.perf_counter() - t)*1000, False)
    tasks = [asyncio.create_task(call()) for _ in range(n)]
    await asyncio.gather(*tasks)
    result.report()
    return result

# ─── Test 3: POST Tasks ──────────────────────────────────────────────────────
async def test_create_tasks(client: httpx.AsyncClient) -> tuple[str, str]:
    sub("Criar Tasks — POST /tasks/dev  +  POST /tasks/marketing")
    dev_id = mkt_id = None

    # Dev task
    t = time.perf_counter()
    try:
        r = await client.post(
            f"{BASE_URL}/tasks/dev",
            json={"request": "Criar uma API REST de autenticação com JWT, refresh tokens e rate limiting. Incluir testes unitários com cobertura > 80%.", "priority": 1},
            timeout=10,
        )
        lat = (time.perf_counter()-t)*1000
        data = r.json()
        dev_id = data.get("task_id")
        ok(f"Dev task criada em {lat:.0f}ms → {dev_id[:16]}...")
    except Exception as e:
        err(f"Dev task falhou: {e}")

    # Marketing task
    t = time.perf_counter()
    try:
        r = await client.post(
            f"{BASE_URL}/tasks/marketing",
            json={"request": "Criar campanha de lançamento para produto SaaS B2B: estratégia, copy para email, posts LinkedIn e análise de KPIs.", "priority": 1},
            timeout=10,
        )
        lat = (time.perf_counter()-t)*1000
        data = r.json()
        mkt_id = data.get("task_id")
        ok(f"Marketing task criada em {lat:.0f}ms → {mkt_id[:16]}...")
    except Exception as e:
        err(f"Marketing task falhou: {e}")

    return dev_id, mkt_id

# ─── Test 4: Task polling ─────────────────────────────────────────────────────
async def poll_task(client: httpx.AsyncClient, task_id: str, team: str,
                    timeout_s: int = 300) -> dict:
    """Aguarda task concluir com polling e mostra progresso."""
    if not task_id:
        return {}
    sub(f"Monitorando task {team} ({task_id[:16]}...) — timeout {timeout_s}s")
    start = time.time()
    last_subtask = -1
    polls = 0
    while time.time() - start < timeout_s:
        try:
            r = await client.get(f"{BASE_URL}/tasks/{task_id}", timeout=5)
            state = r.json()
            polls += 1
            idx   = state.get("current_subtask_index", 0)
            total = len(state.get("subtasks", []))
            errs  = state.get("errors", [])
            output = state.get("final_output")

            if idx != last_subtask and total > 0:
                last_subtask = idx
                elapsed = time.time() - start
                directive = (state.get("senior_directive") or "")[:60]
                info(f"[{elapsed:5.0f}s] Subtarefa {idx}/{total}  |  {directive}...")

            if output:
                elapsed = time.time() - start
                ok(f"Task concluida em {elapsed:.1f}s  |  Output: {len(output)} chars  |  Polls: {polls}")
                if errs:
                    warn(f"Erros encontrados: {len(errs)}")
                    for e in errs[:3]:
                        warn(f"  {e[:80]}")
                # Show snippet
                snippet = output[:300].replace('\n', ' ')
                info(f"Output snippet: {snippet}...")
                return state

        except Exception as e:
            warn(f"Polling erro: {e}")

        await asyncio.sleep(5)

    warn(f"Timeout ({timeout_s}s) — task ainda em execucao")
    return {}

# ─── Test 5: WebSocket ────────────────────────────────────────────────────────
async def test_websocket(timeout_s: int = 15) -> dict:
    sub(f"WebSocket — ws://localhost:8000/ws  ({timeout_s}s listen)")
    events_received = []
    latencies = []
    try:
        async with websockets.connect(WS_URL, ping_interval=10, open_timeout=5) as ws:
            ok("WebSocket conectado")
            deadline = time.time() + timeout_s
            connect_time = time.time()
            while time.time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=2)
                    lat = (time.time() - connect_time)*1000
                    latencies.append(lat)
                    evt = json.loads(raw)
                    events_received.append(evt)
                    etype = evt.get("event_type","?")
                    agent = evt.get("agent_id","?")[:12]
                    info(f"  Event: {C}{etype}{RST}  agent={agent}  lat={lat:.0f}ms")
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    warn(f"WS recv erro: {e}")
                    break

    except Exception as e:
        err(f"WebSocket falhou: {e}")
        return {"events": 0, "error": str(e)}

    ok(f"WebSocket: {len(events_received)} eventos recebidos em {timeout_s}s")
    if latencies:
        info(f"Latencia first-event: {latencies[0]:.0f}ms | avg: {statistics.mean(latencies):.0f}ms")
    return {"events": len(events_received), "types": list({e.get("event_type") for e in events_received})}

# ─── Test 6: Agents endpoint ──────────────────────────────────────────────────
async def test_agents_endpoint(client: httpx.AsyncClient) -> list:
    sub("GET /agents — lista agentes registrados")
    try:
        r = await client.get(f"{BASE_URL}/agents", timeout=5)
        agents = r.json()
        if agents:
            ok(f"{len(agents)} agentes registrados:")
            for ag in agents:
                status_c = G if ag.get("status") == "working" else Y if ag.get("status") == "thinking" else DIM
                print(f"    {status_c}● {ag.get('role','?')}{RST}  [{ag.get('team','?')}]  "
                      f"status={ag.get('status','?')}  tasks_done={ag.get('completed_tasks',0)}")
        else:
            info("Nenhum agente registrado ainda (tasks ainda em planning)")
        return agents
    except Exception as e:
        err(f"Agents endpoint: {e}")
        return []

# ─── Test 7: Concurrent tasks ─────────────────────────────────────────────────
async def test_concurrent_tasks(client: httpx.AsyncClient, n: int = 4) -> PerfResult:
    sub(f"Concurrent POST /tasks/dev  ({n}x simultaneo)")
    result = PerfResult(f"POST /tasks/dev x{n}")
    tasks = []
    async def create(i: int):
        t = time.perf_counter()
        try:
            r = await client.post(
                f"{BASE_URL}/tasks/dev",
                json={"request": f"Tarefa concorrente {i}: Implementar endpoint REST CRUD para entidade Produto com validacao Pydantic.", "priority": 2},
                timeout=10,
            )
            result.record((time.perf_counter()-t)*1000, r.status_code == 202)
        except Exception:
            result.record((time.perf_counter()-t)*1000, False)
    await asyncio.gather(*[asyncio.create_task(create(i)) for i in range(n)])
    result.report()
    return result

# ─── Summary ──────────────────────────────────────────────────────────────────
def print_summary(health: dict, ws: dict, dev_state: dict, mkt_state: dict,
                  stress: PerfResult, conc: PerfResult):
    hdr("RELATORIO DE PERFORMANCE — IRIS AI Office System")

    print(f"\n  {BOLD}Infraestrutura:{RST}")
    api    = G + "ONLINE"  + RST if health.get("api") == "online"  else R + "OFFLINE" + RST
    redis  = G + "ONLINE"  + RST if health.get("redis") == "online" else Y + "FAKEREDIS" + RST
    ollama = G + "ONLINE"  + RST if health.get("ollama") == "online" else Y + "OFFLINE" + RST
    print(f"    FastAPI:  {api}")
    print(f"    Redis:    {redis}")
    print(f"    Ollama:   {ollama}  ({len(health.get('available_models',[]))} modelos)")

    print(f"\n  {BOLD}Latencias de API:{RST}")
    stress.report()
    conc.report()

    print(f"\n  {BOLD}WebSocket:{RST}")
    if ws.get("error"):
        err(f"  Falhou: {ws['error']}")
    else:
        ok(f"  {ws.get('events',0)} eventos recebidos")
        types = [t for t in ws.get("types", []) if t]
        if types:
            info(f"  Tipos: {', '.join(types)}")

    print(f"\n  {BOLD}Tasks Executadas:{RST}")
    for team, state in [("DEV", dev_state), ("MARKETING", mkt_state)]:
        if not state:
            warn(f"  {team}: nao concluida ou timeout")
            continue
        output_len = len(state.get("final_output") or "")
        subtasks   = len(state.get("subtasks") or [])
        errors     = len(state.get("errors") or [])
        col = G if errors == 0 else Y
        print(f"    {col}[{team}]{RST}  subtasks={subtasks}  output={output_len} chars  erros={errors}")

    print(f"\n{C}{'='*60}{RST}")
    print(f"{BOLD}{G}  Teste concluido!{RST}")
    print(f"{C}{'='*60}{RST}\n")

# ─── Main ─────────────────────────────────────────────────────────────────────
async def main():
    global BASE_URL, WS_URL
    for arg in sys.argv[1:]:
        if arg.startswith("--base-url="):
            BASE_URL = arg.split("=", 1)[1]
            WS_URL   = BASE_URL.replace("http://", "ws://") + "/ws"

    hdr("IRIS — Iniciando Suite de Performance")
    print(f"  Backend: {C}{BASE_URL}{RST}")
    print(f"  WS:      {C}{WS_URL}{RST}")

    async with httpx.AsyncClient() as client:
        # 1. Health
        health = await test_health(client)
        if not health:
            err("Backend nao respondeu. Certifique-se que o servidor esta rodando.")
            err("Execute: .venv\\Scripts\\python.exe -m uvicorn backend.api.main:app --port 8000")
            return

        # 2. Stress test
        stress = await test_endpoint_stress(client, n=20)

        # 3. Create tasks (ambos os times em paralelo)
        dev_id, mkt_id = await test_create_tasks(client)

        # 4. Concurrent tasks
        conc = await test_concurrent_tasks(client, n=4)

        # 5. WebSocket (em paralelo com polling)
        ws_task = asyncio.create_task(test_websocket(timeout_s=20))

        # 6. Poll tasks (max 4min por task)
        dev_state, mkt_state = {}, {}
        if dev_id:
            dev_state = await poll_task(client, dev_id, "DEV", timeout_s=240)
        if mkt_id:
            mkt_state = await poll_task(client, mkt_id, "MARKETING", timeout_s=240)

        # 7. Agents endpoint
        await test_agents_endpoint(client)

        # 8. Wait for WebSocket results
        ws_result = await ws_task

    # Summary
    print_summary(health, ws_result, dev_state, mkt_state, stress, conc)

if __name__ == "__main__":
    asyncio.run(main())
