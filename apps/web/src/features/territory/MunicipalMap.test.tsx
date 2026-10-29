import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mapHarness = vi.hoisted(() => {
  const instances: Array<{
    handlers: Record<string, Array<() => void>>;
    sources: Map<string, { data: unknown; setData: ReturnType<typeof vi.fn> }>;
    layers: Set<string>;
    fitBounds: ReturnType<typeof vi.fn>;
    resize: ReturnType<typeof vi.fn>;
    remove: ReturnType<typeof vi.fn>;
    addSource: ReturnType<typeof vi.fn>;
    addLayer: ReturnType<typeof vi.fn>;
    getSource: (id: string) => { data: unknown; setData: unknown } | undefined;
    getLayer: ReturnType<typeof vi.fn>;
    setFilter: ReturnType<typeof vi.fn>;
    on: ReturnType<typeof vi.fn>;
    getCanvas: ReturnType<typeof vi.fn>;
    emit: (name: string) => void;
  }> = [];
  const ResizeObserverMock = vi.fn(function (this: { callback: () => void; observe: ReturnType<typeof vi.fn>; disconnect: ReturnType<typeof vi.fn> }, callback: () => void) {
    this.callback = callback;
    this.observe = vi.fn();
    this.disconnect = vi.fn();
  });
  return { instances, ResizeObserverMock };
});

vi.mock("maplibre-gl", () => ({
  setWorkerUrl: vi.fn(),
  NavigationControl: class {},
  Map: class {
    handlers: Record<string, Array<() => void>> = {};
    sources = new globalThis.Map<string, { data: unknown; setData: ReturnType<typeof vi.fn> }>();
    layers = new Set<string>();
    fitBounds = vi.fn();
    resize = vi.fn();
    remove = vi.fn();
    addSource = vi.fn((id: string, source: { data: unknown }) => {
      this.sources.set(id, { data: source.data, setData: vi.fn((data: unknown) => { this.sources.get(id)!.data = data; }) });
    });
    addLayer = vi.fn((layer: { id: string }) => this.layers.add(layer.id));
    getSource = vi.fn((id: string) => this.sources.get(id));
    getLayer = vi.fn((id: string) => this.layers.has(id) ? { id } : undefined);
    setFilter = vi.fn();
    addControl = vi.fn();
    on = vi.fn((name: string, callback: () => void) => { (this.handlers[name] ??= []).push(callback); });
    getCanvas = vi.fn(() => ({ style: {} }));
    emit(name: string) { this.handlers[name]?.forEach((callback) => callback()); }
    constructor() { mapHarness.instances.push(this); }
  },
}));

import { MunicipalMap } from "./MunicipalMap";
import type { ElectionYear } from "../../app/filters";
import type { HistoryDTO, MunicipalityFeatureCollection, NationalStateFeatureCollection } from "../../lib/api";

function geometry(stateCode: string, code: string, x: number): MunicipalityFeatureCollection {
  return { type: "FeatureCollection", features: [{ type: "Feature", geometry: { type: "Polygon", coordinates: [[[x, 20], [x + 1, 20], [x + 1, 21], [x, 21], [x, 20]]] }, properties: { state_code: stateCode, municipality_code: code, name: `Municipio ${stateCode}` } }] };
}

function outline(stateCode: string, x: number): NationalStateFeatureCollection {
  return { type: "FeatureCollection", features: [{ type: "Feature", geometry: { type: "Polygon", coordinates: [[[x, 18], [x + 2, 18], [x + 2, 22], [x, 22], [x, 18]]] }, properties: { state_code: stateCode, name: stateCode } }] };
}

function observation(stateCode: string, year: number, abstention: number): HistoryDTO {
  return { state_code: stateCode, year, municipality_code: "001", abstention_pct: abstention, participation_pct: 100 - abstention, unknown_share: 0 } as HistoryDTO;
}

function props(overrides: Partial<React.ComponentProps<typeof MunicipalMap>> = {}): React.ComponentProps<typeof MunicipalMap> {
  return {
    year: 2024 as ElectionYear, stateName: "Jalisco", features: geometry("14", "001", -104),
    observations: [observation("14", 2024, 31)], stateOutline: outline("14", -105),
    observationsLoading: false, observationsError: false, stateOutlineLoading: false, stateCode: "14", featuresLoading: false,
    featuresError: false, stateOutlineError: false, selectedMunicipalityCode: null,
    onSelectMunicipality: vi.fn(), ...overrides,
  };
}

describe("MunicipalMap MapLibre sources and camera", () => {
  beforeEach(() => {
    mapHarness.instances.length = 0;
    vi.stubGlobal("WebGLRenderingContext", class {});
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({} as WebGLRenderingContext);
    vi.stubGlobal("ResizeObserver", mapHarness.ResizeObserverMock);
    mapHarness.ResizeObserverMock.mockClear();
  });

  it("updates state outline and bounds when moving from Jalisco to Nuevo León", async () => {
    const view = render(<MunicipalMap {...props()} />);
    await waitFor(() => expect(mapHarness.instances).toHaveLength(1));
    const map = mapHarness.instances[0]!;
    act(() => map.emit("load"));
    await waitFor(() => expect(map.getSource("municipalities")).toBeTruthy());
    map.fitBounds.mockClear();

    view.rerender(<MunicipalMap {...props({ stateCode: "19", stateName: "Nuevo León", features: geometry("19", "001", -100), observations: [observation("19", 2024, 42)], stateOutline: outline("19", -101) })} />);

    await waitFor(() => expect(map.getSource("state-outline")?.data).toMatchObject({ features: [{ properties: { state_code: "19" } }] }));
    expect(map.getSource("municipalities")?.data).toMatchObject({ features: [{ properties: { state_code: "19", abstention_pct: 42 } }] });
    expect(map.fitBounds).toHaveBeenCalledWith([[-101, 18], [-99, 22]], { padding: 28, duration: 0 });
  });

  it("does not recenter for year or municipality changes, and resize refits current bounds then disconnects/removes", async () => {
    const initial = props();
    const view = render(<MunicipalMap {...initial} />);
    await waitFor(() => expect(mapHarness.instances).toHaveLength(1));
    const map = mapHarness.instances[0]!;
    act(() => map.emit("load"));
    await waitFor(() => expect(map.getSource("municipalities")).toBeTruthy());
    map.fitBounds.mockClear();

    view.rerender(<MunicipalMap {...initial} year={2021} observations={[observation("14", 2021, 48)]} />);
    view.rerender(<MunicipalMap {...initial} year={2021} observations={[observation("14", 2021, 48)]} selectedMunicipalityCode="001" />);
    expect(map.getSource("municipalities")?.data).toMatchObject({ features: [{ properties: { abstention_pct: 48 } }] });
    expect(map.fitBounds).not.toHaveBeenCalled();
    expect(map.setFilter).toHaveBeenCalledWith("municipalities-selected", ["==", ["get", "municipality_code"], "001"]);

    const resizeObserver = mapHarness.ResizeObserverMock.mock.instances.at(-1) as unknown as { callback: () => void; disconnect: ReturnType<typeof vi.fn> };
    act(() => resizeObserver.callback());
    expect(map.resize).toHaveBeenCalledOnce();
    expect(map.fitBounds).toHaveBeenCalledWith([[-105, 18], [-103, 22]], { padding: 28, duration: 0 });
    view.unmount();
    expect(resizeObserver.disconnect).toHaveBeenCalledOnce();
    expect(map.remove).toHaveBeenCalledOnce();
  });

  it("drops cached observations from both map and table when refetch errors", async () => {
    const view = render(<MunicipalMap {...props({ featuresError: false })} />);
    await waitFor(() => expect(mapHarness.instances).toHaveLength(1));
    const map = mapHarness.instances[0]!;
    act(() => map.emit("load"));
    await waitFor(() => expect(map.getSource("municipalities")).toBeTruthy());
    expect(map.getSource("municipalities")?.data).toMatchObject({ features: [{ properties: { abstention_pct: 31 } }] });
    view.rerender(<MunicipalMap {...props({ observationsError: true, featuresError: false })} />);
    expect(map.getSource("municipalities")?.data).toMatchObject({ features: [{ properties: { abstention_pct: null, participation_pct: null } }] });
    expect(screen.getByRole("alert")).toHaveTextContent("No se pudieron cargar las observaciones");
    expect(screen.queryByText("31.0 %")).not.toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
  });
});
