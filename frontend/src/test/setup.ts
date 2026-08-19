import "@testing-library/jest-dom/vitest";

if (!URL.createObjectURL) {
  URL.createObjectURL = () => "blob:city-os-test-worker";
}

if (!URL.revokeObjectURL) {
  URL.revokeObjectURL = () => undefined;
}
