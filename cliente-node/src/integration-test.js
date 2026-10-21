const grpc = require("@grpc/grpc-js");
const { createClient, unaryCall } = require("./grpc-client");

async function listar(client, deadline) {
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
  const connection = createClient({
    defaultAddress: "equipos-api:50051",
    defaultTimeoutMs: 5000,
  });
  const { client, deadline } = connection;

  try {
    const total = await listar(client, deadline);
    console.log(`OK ListarEquipos: ${total} equipo(s) recibidos`);

    try {
      await unaryCall(client, deadline, "consultarEquipo", { id: 999999 });
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
