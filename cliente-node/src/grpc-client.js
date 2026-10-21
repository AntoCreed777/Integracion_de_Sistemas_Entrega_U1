const path = require("node:path");
const grpc = require("@grpc/grpc-js");
const protoLoader = require("@grpc/proto-loader");

// Esto esta pensado para funcionar en el contenedor de Docker, donde el .proto se encuentra en la raíz del proyecto. Si se ejecuta localmente, es posible que se necesite ajustar la ruta según tu estructura de carpetas.
const PROTO_PATH = path.resolve(__dirname, "../equipos.proto");

const packageDefinition = protoLoader.loadSync(PROTO_PATH, {
  keepCase: false,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true,
});

const grpcPackage = grpc.loadPackageDefinition(packageDefinition);
const Client = grpcPackage.equipos.v1.ServicioEquipos;

function getTimeoutMs(defaultTimeoutMs) {
  const timeoutMs = Number.parseInt(
    process.env.GRPC_TIMEOUT_MS || String(defaultTimeoutMs),
    10,
  );

  if (!Number.isInteger(timeoutMs) || timeoutMs <= 0) {
    throw new Error("GRPC_TIMEOUT_MS debe ser un entero mayor que cero");
  }

  return timeoutMs;
}

function createClient({
  defaultAddress = "localhost:50051",
  defaultTimeoutMs = 3000,
} = {}) {
  const address = process.env.EQUIPOS_GRPC_URL || defaultAddress;
  const timeoutMs = getTimeoutMs(defaultTimeoutMs);

  return {
    client: new Client(address, grpc.credentials.createInsecure()),
    deadline: () => new Date(Date.now() + timeoutMs),
  };
}

function unaryCall(client, deadline, methodName, request) {
  return new Promise((resolve, reject) => {
    client[methodName](request, { deadline: deadline() }, (error, response) => {
      if (error) {
        reject(error);
        return;
      }
      resolve(response);
    });
  });
}

module.exports = { createClient, unaryCall };
