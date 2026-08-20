"use client";

import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { CityMap } from "@/features/map/CityMap";
import { createCityMapViewModel } from "@/features/map/layers";
import { ComparisonPanel } from "@/features/metrics/ComparisonPanel";
import {
  ScenarioPanel,
  scenarioCardsFromObservations,
} from "@/features/scenarios/ScenarioPanel";
import { SensorComposer } from "@/features/scenarios/SensorComposer";
import { FleetControl } from "@/features/simulation/FleetControl";
import { PlaybackControls } from "@/features/simulation/PlaybackControls";
import { useSimulation } from "@/features/simulation/useSimulation";
import { HttpCityOsTransport } from "@/lib/api/http-transport";
import { MockCityOsTransport } from "@/lib/api/mock-transport";
import type { CityMapData, CityOsTransport } from "@/lib/api/transport";
import type {
  BootstrapResponse,
  ScenarioObservation,
  SimulationRequest,
} from "@/lib/contracts/generated";

function createTransport(): CityOsTransport {
  return process.env.NEXT_PUBLIC_CITY_OS_API_URL
    ? new HttpCityOsTransport()
    : new MockCityOsTransport({ frameIntervalMs: 90, defaultFleetSize: 35 });
}

export function Portal() {
  const transport = useMemo(createTransport, []);
  const [bootstrap, setBootstrap] = useState<BootstrapResponse | null>(null);
  const [bootstrapError, setBootstrapError] = useState<string | null>(null);
  const [mapData, setMapData] = useState<CityMapData | null>(null);
  const [selectedScenarioId, setSelectedScenarioId] = useState("");
  const [observations, setObservations] = useState<ScenarioObservation[]>([]);
  const [pendingRequest, setPendingRequest] = useState<SimulationRequest | null>(null);
  const simulation = useSimulation(transport, {
    durationMinutes: bootstrap?.simulation_duration_minutes ?? 360,
  });

  useEffect(() => {
    let active = true;
    void transport.bootstrap().then((value) => {
      if (!active) return;
      setBootstrap(value);
      if (process.env.NEXT_PUBLIC_CITY_OS_API_URL) {
        void transport.loadMapData(value.layer_urls as Record<string, string>)
          .then((data) => { if (active) setMapData(data); })
          .catch((error: unknown) => {
            if (active) setBootstrapError(error instanceof Error ? error.message : "Falha ao carregar o mapa da API.");
          });
      }
      setObservations(value.scenarios);
      setSelectedScenarioId(value.scenarios[0]?.id ?? "");
      const initialScenario = value.scenarios[0];
      setPendingRequest(initialScenario ? {
        scenario_id: initialScenario.id,
        fleet_size: value.fleet_size_bounds.default,
        seed: value.default_seed,
      } : null);
    }).catch((error: unknown) => {
      if (active) {
        setBootstrapError(error instanceof Error ? error.message : "Falha ao carregar o City OS.");
      }
    });
    return () => {
      active = false;
    };
  }, [transport]);

  if (bootstrapError) {
    return (
      <main className="portal-state" role="alert">
        <p className="eyebrow">City OS indisponível</p>
        <h1>O portal não pôde iniciar</h1>
        <p>{bootstrapError}</p>
      </main>
    );
  }

  if (!bootstrap) {
    return (
      <main className="portal-state" aria-busy="true">
        <p className="eyebrow">City OS</p>
        <h1>Preparando a cidade…</h1>
        <p>Validando contratos e carregando os ativos locais.</p>
      </main>
    );
  }

  const currentFrame = simulation.currentFrames.optimized ?? simulation.currentFrames.baseline;
  const activeScenarioIds = currentFrame?.active_scenario_ids ?? [];
  const repositioningUnits = simulation.currentFrames.optimized?.ambulances.filter(
    (ambulance) => ambulance.status === "repositioning",
  ).length ?? 0;
  const request = pendingRequest ?? {
    scenario_id: selectedScenarioId,
    fleet_size: bootstrap.fleet_size_bounds.default,
    seed: bootstrap.default_seed,
  };
  const run = (nextRequest: SimulationRequest = request) => {
    setPendingRequest(nextRequest);
    void simulation.run(nextRequest);
  };

  const header = (
    <div className="portal-header">
      <div>
        <p className="eyebrow">Ambulance Allocation · São Paulo</p>
        <h1>City OS</h1>
      </div>
      <div className="portal-header__meta">
        <span>Seed {request.seed}</span>
        <span>{process.env.NEXT_PUBLIC_CITY_OS_API_URL ? "API local" : "Fixture C0 offline"}</span>
        <span>{simulation.state.job}</span>
      </div>
    </div>
  );

  const controls = (
    <div className="portal-stack">
      <FleetControl
        scenarioId={selectedScenarioId}
        initialFleetSize={request.fleet_size}
        minimum={bootstrap.fleet_size_bounds.minimum}
        maximum={bootstrap.fleet_size_bounds.maximum}
        seed={request.seed}
        disabled={simulation.state.job === "creating"}
        onRun={run}
        onFleetSizeChange={(fleetSize) => setPendingRequest((current) => ({
          scenario_id: current?.scenario_id ?? selectedScenarioId,
          fleet_size: fleetSize,
          seed: current?.seed ?? bootstrap.default_seed,
        }))}
      />
      <SensorComposer
        transport={transport}
        fallbackObservation={observations.find((item) => item.id === selectedScenarioId)}
        onParsed={(observation) => {
          setObservations((current) => current.some((item) => item.id === observation.id)
            ? current
            : [...current, observation]);
          setSelectedScenarioId(observation.id);
          setPendingRequest((current) => ({
            scenario_id: observation.id,
          fleet_size: current?.fleet_size ?? bootstrap.fleet_size_bounds.default,
            seed: current?.seed ?? bootstrap.default_seed,
          }));
        }}
      />
    </div>
  );

  return (
    <AppShell
      header={header}
      controls={controls}
      scenarios={(
        <ScenarioPanel
          scenarios={scenarioCardsFromObservations(observations)}
          selectedScenarioId={selectedScenarioId}
          activeScenarioIds={activeScenarioIds}
          queuedScenarioId={simulation.state.job === "creating" ? selectedScenarioId : null}
          onSelectScenario={(scenarioId) => {
            setSelectedScenarioId(scenarioId);
            setPendingRequest((current) => ({
              scenario_id: scenarioId,
              fleet_size: current?.fleet_size ?? bootstrap.fleet_size_bounds.default,
              seed: current?.seed ?? bootstrap.default_seed,
            }));
          }}
        />
      )}
      map={<CityMap viewModel={createCityMapViewModel(bootstrap, currentFrame, mapData, {
        source: process.env.NEXT_PUBLIC_CITY_OS_API_URL ? "api" : "fixture",
      })} />}
      comparison={(
        <ComparisonPanel
          baseline={simulation.terminalMetrics.baseline}
          optimized={simulation.terminalMetrics.optimized}
        />
      )}
      timeline={(
        <PlaybackControls
          currentMinute={simulation.state.currentMinute}
          durationMinutes={bootstrap.simulation_duration_minutes}
          playing={simulation.state.playing}
          speed={simulation.state.speed}
          job={simulation.state.job}
          connection={simulation.state.connection}
          error={simulation.state.error}
          onRun={() => run()}
          onReset={simulation.reset}
          onPlayingChange={simulation.setPlaying}
          onSpeedChange={simulation.setSpeed}
          onScrub={simulation.scrub}
        />
      )}
    >
      <div className="portal-evidence" data-testid="operational-evidence" aria-live="polite">
        <span>Minuto {Math.round(simulation.state.currentMinute)}</span>
        <span>Cenários ativos: {activeScenarioIds.length ? activeScenarioIds.join(", ") : "nenhum"}</span>
        <span>Ambulâncias preditivas reposicionando: {repositioningUnits}</span>
      </div>
    </AppShell>
  );
}
