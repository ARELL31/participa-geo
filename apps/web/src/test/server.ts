import { setupServer } from "msw/node";

/** MSW is used only by the unit/component suites; E2E always hits the real API. */
export const server = setupServer();
