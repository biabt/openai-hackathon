import Ajv2020, { type ErrorObject, type ValidateFunction } from "ajv/dist/2020";
import contractSchema from "./schema.json";
import type {
  BootstrapResponse,
  ScenarioObservation,
  ScenarioParseResponse,
  SimulationCreatedResponse,
  SimulationFrame,
  SimulationRequest,
  SimulationJobResponse,
} from "./generated";

export interface CityOsContracts {
  BootstrapResponse: BootstrapResponse;
  ScenarioObservation: ScenarioObservation;
  ScenarioParseResponse: ScenarioParseResponse;
  SimulationCreatedResponse: SimulationCreatedResponse;
  SimulationFrame: SimulationFrame;
  SimulationRequest: SimulationRequest;
  SimulationJobResponse: SimulationJobResponse;
}

export type ContractName = keyof CityOsContracts;

export class ContractValidationError extends Error {
  readonly contract: ContractName;
  readonly errors: readonly ErrorObject[];

  constructor(contract: ContractName, errors: readonly ErrorObject[]) {
    const detail = errors.map((error) => `${error.instancePath || "/"} ${error.message ?? "is invalid"}`).join("; ");
    super(`Invalid ${contract}: ${detail}`);
    this.name = "ContractValidationError";
    this.contract = contract;
    this.errors = errors;
  }
}

const ajv = new Ajv2020({ allErrors: true, strict: true });
const validators = new Map<ContractName, ValidateFunction>();

export function validateContract<K extends ContractName>(contract: K, value: unknown): value is CityOsContracts[K] {
  return validatorFor(contract)(value) as boolean;
}

export function assertContract<K extends ContractName>(contract: K, value: unknown): CityOsContracts[K] {
  const validator = validatorFor(contract);
  if (!validator(value)) throw new ContractValidationError(contract, validator.errors ?? []);
  return value as CityOsContracts[K];
}

export function parseJsonLines(text: string): SimulationFrame[] {
  return text
    .split(/\r?\n/u)
    .filter((line) => line.trim().length > 0)
    .map((line, index) => {
      let value: unknown;
      try { value = JSON.parse(line); }
      catch (error) { throw new SyntaxError(`Invalid stream JSON at line ${index + 1}: ${String(error)}`); }
      return assertContract("SimulationFrame", value);
    });
}

function validatorFor(contract: ContractName): ValidateFunction {
  const cached = validators.get(contract);
  if (cached) return cached;

  const validator = ajv.compile({
    $schema: "https://json-schema.org/draft/2020-12/schema",
    $defs: contractSchema.$defs,
    $ref: `#/$defs/${contract}`,
  });
  validators.set(contract, validator);
  return validator;
}
