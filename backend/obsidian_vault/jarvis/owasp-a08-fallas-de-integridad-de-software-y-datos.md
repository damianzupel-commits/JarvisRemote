---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- owasp
- vulnerabilidad
title: OWASP A08 - Fallas de Integridad de Software y Datos
updated: '2026-07-28T00:00:00.000000+00:00'
---

Categoría nueva en el [[OWASP Top 10 - Resumen]] 2021. Cubre código o infraestructura que asume que datos, paquetes o actualizaciones son íntegros (no manipulados) sin verificarlo criptográficamente.

## Patrones concretos
- **Insecure deserialization**: deserializar datos no confiables con un formato que permite ejecución de código como side-effect (`pickle` en Python, `ObjectInputStream` en Java, `unserialize()` en PHP, `yaml.load` sin `Loader` seguro). Nota dedicada con ejemplos: [[Insecure Deserialization]].
- **CI/CD pipeline sin verificación de integridad**: pipeline que hace `curl | bash` de un script de instalación de terceros sin pinear un hash/versión, o que instala dependencias sin lockfile (ver [[OWASP A06 - Componentes Vulnerables y Desactualizados]]).
- **Auto-actualización sin verificar firma**: una app que descarga y ejecuta updates sin verificar la firma criptográfica del paquete contra una clave pública confiable.
- **Uso de plugins/librerías desde repositorios no oficiales** o mirrors no verificados, que pueden servir un paquete distinto al esperado (typosquatting, dependency confusion — un paquete interno con el mismo nombre que uno público puede ser "confundido" si el resolver prioriza el registro público).
- **Cookies o tokens de estado sin firma/HMAC**, que el cliente puede modificar sin que el servidor lo note.

## Ejemplo
```python
# vulnerable: pickle deserializa objetos arbitrarios, puede ejecutar código
import pickle
data = pickle.loads(untrusted_bytes)

# vulnerable: yaml.load sin especificar Loader seguro puede instanciar objetos Python
import yaml
config = yaml.load(untrusted_yaml, Loader=yaml.Loader)  # o sin Loader en versiones viejas

# seguro
config = yaml.safe_load(untrusted_yaml)
```

## Mitigación
Nunca deserializar datos no confiables con formatos que permiten ejecución de código (usar JSON en vez de pickle/yaml.Loader para datos externos); firmar y verificar artefactos de build y actualizaciones (Sigstore/cosign, GPG); pinear versiones exactas (por hash, no solo por tag) en pipelines de CI/CD; usar lockfiles siempre. Ver también [[Herramientas SAST y SCA - Resumen]] para escaneo de la supply chain.
