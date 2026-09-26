# Instrucciones de ejecución

Las siguientes instrucciones asumen que **Docker** y **Docker Compose** se encuentran instalados y que los comandos se ejecutan desde la **raíz del proyecto**.

## Ejecución de los servicios

Para construir las imágenes y levantar los servicios definidos en `docker-compose.yaml`, ejecutar:

```bash
docker compose -f docker-compose.yaml up --build
```

Para detener los contenedores asociados al proyecto:

```bash
docker compose down
```

Si además se desea eliminar los volúmenes asociados a los servicios, lo que implica eliminar los datos persistidos en ellos, ejecutar:

```bash
docker compose down -v
```

> **Advertencia:** el uso de `-v` elimina los volúmenes asociados al proyecto y, por lo tanto, los datos persistidos en ellos.

## Ejecución de las pruebas

Las pruebas pueden ejecutarse mediante la configuración definida en `docker-compose.test.yaml`:

```bash
docker compose -f docker-compose.test.yaml up --build
```

Una vez finalizadas las pruebas, los servicios pueden permanecer activos. Para detenerlos y eliminar los volúmenes generados durante la ejecución de las pruebas:

```bash
docker compose down -v
```

## Verificación de contenedores activos

Para comprobar qué contenedores se encuentran actualmente en ejecución:

```bash
docker ps
```

Si se identifica algún contenedor que permanezca activo y deba ser detenido, se puede utilizar:

```bash
docker stop <id_contenedor>
```

Reemplazando `<id_contenedor>` por el identificador correspondiente.

Una vez detenido el contenedor, si se desea eliminarlo junto con los volúmenes anónimos asociados:

```bash
docker rm -v <id_contenedor>
```

Esta última operación elimina el contenedor y los volúmenes anónimos asociados a él.
