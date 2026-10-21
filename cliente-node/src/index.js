const process = require("node:process");
const grpc = require("@grpc/grpc-js");
const { createClient: createGrpcClient, unaryCall } = require("./grpc-client");

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

async function consultar(client, deadline, id) {
  const equipo = await unaryCall(client, deadline, "consultarEquipo", { id });
  showEquipo(equipo);
}

async function disponibilidad(client, deadline, id) {
  const resultado = await unaryCall(
    client,
    deadline,
    "consultarDisponibilidadEquipo",
    { id },
  );
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

async function listar(client, deadline) {
  const stream = client.listarEquipos({}, { deadline: deadline() });
  let total = 0;

  for await (const equipo of stream) {
    total += 1;
    showEquipo(equipo);
  }

  console.log(`Equipos recibidos: ${total}`);
}

async function reservar(client, deadline, id) {
  await unaryCall(client, deadline, "reservarEquipo", { id });
  console.log(`Reserva realizada para el equipo ${id}`);
}

async function liberar(client, deadline, id) {
  await unaryCall(client, deadline, "liberarEquipo", { id });
  console.log(`Liberación realizada para el equipo ${id}`);
}

async function demo(client, deadline, id) {
  console.log("1) Consultar equipo");
  await consultar(client, deadline, id);

  console.log("\n2) Consultar disponibilidad");
  await disponibilidad(client, deadline, id);

  console.log("\n3) Listar catálogo vía streaming");
  await listar(client, deadline);
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

  const { client, deadline } = createGrpcClient();

  try {
    switch (command) {
      case "consultar": {
        await consultar(client, deadline, parsePositiveInt(arg, "ID del equipo"));
        break;
      }
      case "disponibilidad": {
        await disponibilidad(client, deadline, parsePositiveInt(arg, "ID del equipo"));
        break;
      }
      case "listar": {
        await listar(client, deadline);
        break;
      }
      case "reservar": {
        await reservar(client, deadline, parsePositiveInt(arg, "ID del equipo"));
        break;
      }
      case "liberar": {
        await liberar(client, deadline, parsePositiveInt(arg, "ID del equipo"));
        break;
      }
      case "demo": {
        const id = arg ? parsePositiveInt(arg, "ID del equipo") : 1;
        await demo(client, deadline, id);
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
