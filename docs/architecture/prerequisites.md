# Prerrequisito de ejecución: Docker con Compose

El agente no ha instalado software ni modificado el sistema. El usuario instaló Docker tras la investigación inicial.

## Estado actual verificado

DockerEngine29.9.2 y Compose5.6.1 están instalados; `docker.service` está activo. El acceso a cliente y servidor se comprobó con:

```sh
sg docker -c 'docker version'
```

La cuenta ya pertenece al grupoDocker, pero el proceso de la sesión conserva los grupos anteriores a la instalación. Usar `sg docker -c '<comando>'` en esta sesión habilita la membresía existente sin cambiar permisos del socket. No se necesita reinstalar Docker ni añadir nuevamente el usuario al grupo. Una sesión nueva normalmente recogerá la membresía actual.

Las alternativas siguientes se conservan como referencia histórica, no como instrucciones para instalar otro daemon junto al existente.

Entorno detectado: AlmaLinux10.2, WSL2, systemd, x86_64. En la investigación inicial no se encontró `docker` enPATH; el estado actualizado se describe arriba. Para el diseño propuesto no hace falta Node, PostgreSQL, GeoServer o GDAL instalados en el host: se usarán contenedores una vez aprobado el plan.

## Opción recomendada si se usa DockerDesktop en Windows

Seguir la documentación oficial: https://docs.docker.com/desktop/features/wsl/

1. Instalar o iniciar DockerDesktop para Windows, revisando requisitos y licencia.
2. Activar **Use WSL2 based engine** en General.
3. Activar la distribución de AlmaLinux en **Resources > WSL Integration** y aplicar.
4. Desde la misma distribución donde se ejecuta OpenCode, comprobar:

```sh
docker version
docker compose version
```

Se necesita cliente y servidor accesibles; la versión del cliente por sí sola no prueba acceso al daemon. No ejecutar a la vez DockerEngine nativo dentro de la distribución y DockerDesktop integrado: la documentación advierte posibles conflictos. La integración es una decisión del usuario; este documento no la activa.

## Alternativa: DockerEngine nativo

Documentación oficial de referencia para CentOSStream10/9: https://docs.docker.com/engine/install/centos/

Se comprobó la existencia de paquetes oficialesEL10, pero la guía no declara soporte explícito a AlmaLinux. Confirmar con el usuario que prefiere esta ruta antes de proporcionar/ejecutar comandos de instalación. Evitar instalar herramientas adicionales si DockerDesktop ya resuelve el acceso.

Añadir el usuario al grupoDocker concede privilegios equivalentes aroot; no hacerlo silenciosamente. Alternativas y advertencias: https://docs.docker.com/engine/install/linux-postinstall/

No desactivar SELinux, no abrir puertos de firewall, no publicar el socketDocker porTCP y no ejecutar `curl|sh` como atajo.
