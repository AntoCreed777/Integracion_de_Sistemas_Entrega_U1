const grpc = require("@grpc/grpc-js");
const protoLoader = require("@grpc/proto-loader");
const path = require("node:path");

const address = process.env.EQUIPOS_GRPC_URL || "equipos-api:50051";
const timeoutMs = Number.parseInt(process.env.GRPC_TIMEOUT_MS || "5000", 10);
const protoPath = path.resolve(__dirname, "../../Equipos/equipos.proto");

const definition = protoLoader.loadSync(protoPath, {
  keepCase: false,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true,
});

const grpcPackage = grpc.loadPackageDefinition(definition);
const Client = grpcPackage.equipos.v1.ServicioEquipos;

function deadline() {
  return new Date(Date.now() + timeoutMs);
}

function unary(client, method, request) {
  return new Promise((resolve, reject) => {
    client[method](request, { deadline: deadline() }, (error, response) => {
      if (error) {
        reject(error);
        return;
      }
      resolve(response);
    });
  });
}

async function listar(client) {
  const stream = client.listarEquipos({}, { deadline: deadline() });
  let total = 0;

  for await (const equipo of stream) {
    if (!Number.isInteger(equipo.id)) {
      throw new Error("El stream devolvió un equipo sin ID entero");
    }
    total += 1;
  }

  return total;
}

async function main() {
  const client = new Client(
    address,
    grpc.credentials.createInsecure(),
  );

  try {
    const total = await listar(client);
    console.log(`OK ListarEquipos: ${total} equipo(s) recibidos`);

    try {
      await unary(client, "consultarEquipo", { id: 999999 });
      throw new Error("ConsultarEquipo debía responder NOT_FOUND");
    } catch (error) {
      if (error.code !== grpc.status.NOT_FOUND) {
        throw error;
      }
      console.log("OK ConsultarEquipo: NOT_FOUND manejado correctamente");
    }

    console.log("Pruebas de interoperabilidad Node.js <-> Python: OK");
  } finally {
    client.close();
  }
}

main().catch((error) => {
  console.error(`Pruebas de interoperabilidad: ERROR - ${error.message}`);
  process.exitCode = 1;
});
