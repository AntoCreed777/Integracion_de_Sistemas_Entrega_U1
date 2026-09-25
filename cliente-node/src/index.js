const path = require("node:path");
const process = require("node:process");
const grpc = require("@grpc/grpc-js");
const protoLoader = require("@grpc/proto-loader");

const PROTO_PATH = path.resolve(__dirname, "../../Equipos/equipos.proto");
const ADDRESS = process.env.EQUIPOS_GRPC_URL || "localhost:50051";
const TIMEOUT_MS = Number.parseInt(process.env.GRPC_TIMEOUT_MS || "3000", 10);

if (!Number.isInteger(TIMEOUT_MS) || TIMEOUT_MS <= 0) {
  throw new Error("GRPC_TIMEOUT_MS debe ser un entero mayor que cero");
}

const packageDefinition = protoLoader.loadSync(PROTO_PATH, {
  keepCase: false,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true,
});

const equiposProto = grpc.loadPackageDefinition(packageDefinition);
const { equipos } = equiposProto;
const { v1: equipoV1 } = equipos;

function createClient() {
  return new equipoV1.ServicioEquipos(
    ADDRESS,
    grpc.credentials.createInsecure(),
  );
}

function buildDeadline() {
  return new Date(Date.now() + TIMEOUT_MS);
}

function describeError(error) {
  if (!error) {
    return "Error desconocido";
  }

  const codeName = grpc.status[error.code] || error.code;
  return `${codeName}: ${error.details || error.message || "Sin detalle"}`;
}

function parsePositiveInt(value, label = "ID") {
  const numeric = Number.parseInt(value, 10);
  if (!Number.isInteger(numeric) || numeric <= 0) {
    throw new Error(`${label} debe ser un entero positivo`);
  }
  return numeric;
}

function showEquipo(equipo) {
  console.log(
    JSON.stringify(
      {
        id: equipo.id,
        nombre: equipo.nombre,
        descripcion: equipo.descripcion,
        unidadesDisponibles: equipo.unidadesDisponibles,
      },
      null,
      2,
    ),
  );
}

function unaryCall(client, methodName, request) {
  return new Promise((resolve, reject) => {
    client[methodName](request, { deadline: buildDeadline() }, (error, response) => {
      if (error) {
        reject(error);
        return;
      }
      resolve(response);
    });
  });
}

async function consultar(client, id) {
  const equipo = await unaryCall(client, "consultarEquipo", { id });
  showEquipo(equipo);
}

async function disponibilidad(client, id) {
  const resultado = await unaryCall(client, "consultarDisponibilidadEquipo", { id });
  console.log(
    JSON.stringify(
      {
        id: resultado.id,
        unidadesDisponibles: resultado.unidadesDisponibles,
      },
      null,
      2,
    ),
  );
}

async function listar(client) {
  const stream = client.listarEquipos({}, { deadline: buildDeadline() });
  let total = 0;

  for await (const equipo of stream) {
    total += 1;
    showEquipo(equipo);
  }

  console.log(`Equipos recibidos: ${total}`);
}

async function reservar(client, id) {
  await unaryCall(client, "reservarEquipo", { id });
  console.log(`Reserva realizada para el equipo ${id}`);
}

async function liberar(client, id) {
  await unaryCall(client, "liberarEquipo", { id });
  console.log(`Liberación realizada para el equipo ${id}`);
}

async function demo(client, id) {
  console.log("1) Consultar equipo");
  await consultar(client, id);

  console.log("\n2) Consultar disponibilidad");
  await disponibilidad(client, id);

  console.log("\n3) Listar catálogo vía streaming");
  await listar(client);
}

function printHelp() {
  console.log(`Uso:
  node src/index.js consultar <id>
  node src/index.js disponibilidad <id>
  node src/index.js listar
  node src/index.js reservar <id>
  node src/index.js liberar <id>
  node src/index.js demo [id]

Variables de entorno:
  EQUIPOS_GRPC_URL   Dirección del servicio (default: localhost:50051)
  GRPC_TIMEOUT_MS    Timeout del cliente en ms (default: 3000)

Ejemplos:
  node src/index.js consultar 1
  EQUIPOS_GRPC_URL=equipos-api:50051 node src/index.js listar
`);
}

async function main() {
  const [, , command, arg] = process.argv;

  if (!command || command === "--help" || command === "-h") {
    printHelp();
    return;
  }

  const client = createClient();

  try {
    switch (command) {
      case "consultar": {
        await consultar(client, parsePositiveInt(arg, "ID del equipo"));
        break;
      }
      case "disponibilidad": {
        await disponibilidad(client, parsePositiveInt(arg, "ID del equipo"));
        break;
      }
      case "listar": {
        await listar(client);
        break;
      }
      case "reservar": {
        await reservar(client, parsePositiveInt(arg, "ID del equipo"));
        break;
      }
      case "liberar": {
        await liberar(client, parsePositiveInt(arg, "ID del equipo"));
        break;
      }
      case "demo": {
        const id = arg ? parsePositiveInt(arg, "ID del equipo") : 1;
        await demo(client, id);
        break;
      }
      default:
        printHelp();
        process.exitCode = 1;
        break;
    }
  } catch (error) {
    console.error(`Error gRPC: ${describeError(error)}`);
    process.exitCode = 1;
  } finally {
    client.close();
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
