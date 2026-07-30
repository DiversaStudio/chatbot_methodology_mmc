# **📝 Las notas**

jul 28, 2026

## **MMC chatbot v2**

Invitado [Francisco Gallegos](mailto:francisco@diversa.studio) [Juan Daniel Vasconez](mailto:juanda@diversa.studio)

Archivos adjuntos [MMC chatbot v2](https://calendar.google.com/calendar/event?eid=NjI4ZWhtdTYza3NvY2swa2IwYjJ2ZzNsMDcganVhbmRhQGRpdmVyc2Euc3R1ZGlv)

Registros de la reunión [Transcripción](https://docs.google.com/document/d/1kZlk1fWF5-G2iGNKN0uIaNL5cEmzQbua7fHXFtl9-O4/edit?usp=drive_web&tab=t.yi0dhsmuleet) 

### **Resumen**

Definición de métricas de desempeño y visualización del tablero con validación de modelos técnicos.

**Cálculo de indicadores clave**  
Se discutió la integración de 2 gráficos para visualizar el promedio de calificación y el desglose de respuestas. El conteo de conversaciones por usuario se evaluó como una métrica precisa.

**Definición del tiempo promedio**  
El tiempo promedio de sesión, calculado desde la creación del registro hasta el último mensaje, se definió como la métrica oficial para el segundo indicador de desempeño.

**Optimización del flujo técnico**  
Se analizaron ajustes en la categorización del flujo de datos. Se requiere una revisión detallada de los resultados generados por el modelo para garantizar la precisión técnica.

### **Próximos pasos**

- [ ] \[Juan Daniel Vasconez\] Preparar exports: Preparar los archivos de exportación nuevamente para el análisis de datos.

- [ ] \[Juan Daniel Vasconez\] Crear gráficos: Realizar los gráficos necesarios para el tablero una vez listos los archivos.

- [ ] \[Juan Daniel Vasconez\] Finalizar pestaña: Finalizar la última pestaña del proyecto.

- [ ] \[Juan Daniel Vasconez\] Revisar resultados: Revisar los resultados generados por el modelo para verificar que no contengan errores.

### **Detalles**

* **KPI3: Cálculo y visualización**: Francisco Gallegos y Juan Daniel Vasconez discuten el cálculo del KPI3, el cual consiste en obtener un promedio de una escala del 1 al 5 de la variable de calificación del servicio. Estiman que el puntaje es aproximadamente de 4.1 basándose en 32 de 69 respuestas. Acuerdan incluir dos gráficos en el tablero: uno que muestre el promedio y otro con el desglose detallado de las respuestas ([00:00:01](#00:00:01)).

* **Métricas de mensajes y conversaciones**: Los participantes conversan sobre el volumen de mensajes y la necesidad de medir las conversaciones. Francisco Gallegos y Juan Daniel Vasconez determinan que es útil contar el número de conversaciones por usuario, aclarando que, dado que normalmente hay solo una conversación por usuario, esta métrica es precisa y relevante para el análisis ([00:01:10](#00:01:10)).

* **Definición de KPI2 y tiempo promedio de sesión**: Francisco Gallegos y Juan Daniel Vasconez analizan posibles métricas para el KPI2, evaluando opciones como el volumen de mensajes o el tiempo de sesión. Concluyen que el tiempo promedio de sesión, calculado desde la creación del registro hasta el último mensaje, es una métrica adecuada a largo plazo, a pesar de que los datos actuales de julio puedan estar sesgados ([00:02:11](#00:02:11)). Confirman que los datos para el tiempo de sesión están completos y deciden utilizar esta métrica ([00:05:30](#00:05:30)).

* **Plazos y planificación del tablero**: Francisco Gallegos y Juan Daniel Vasconez revisan el impacto de las actualizaciones en el tablero y el proceso de trabajo. Establecen como plazo límite el día de mañana para finalizar las tareas pendientes. Juan Daniel Vasconez se compromete a preparar las exportaciones hoy mismo y a completar la creación de los gráficos y la pestaña final del tablero para el día siguiente ([00:07:23](#00:07:23)).

* **Actualizaciones del flujo de datos y modelo técnico**: Se discuten los cambios necesarios en el flujo de datos (pipeline), que incluyen la modificación de encabezados y el orden de ciertas variables. Francisco Gallegos y Juan Daniel Vasconez acuerdan mantener la categorización actual como sugerencias para asegurar la claridad del análisis ([00:07:23](#00:07:23)). Juan Daniel Vasconez indica que están utilizando el modelo Claude Opus para estas actualizaciones y acuerdan que se realizará una revisión detallada de los resultados para garantizar que el modelo no genere errores ([00:08:33](#00:08:33)).

*Revisa las notas de Gemini para asegurarte de que sean precisas. [Obtén sugerencias y descubre cómo Gemini toma notas](https://support.google.com/meet/answer/14754931)*

*Cómo es la calidad de **estas notas específicas?** [Responde una breve encuesta](https://google.qualtrics.com/jfe/form/SV_5bXzKQfylMIhSXc?confid=Wsg0OMMnkMVyV3JfqHKuDxIXOAIIigIgABgBCA&detailLevel=standard&hasImages=False&entryPoint=footerMain&isGoogler=False) para darnos tu opinión; por ejemplo, cuán útiles te resultaron las notas.*

# **📖 Transcripción**

jul 28, 2026

## **MMC chatbot v2 \- Transcripción**

### **00:00:01** {#00:00:01}

**Francisco Gallegos:** Eh,

**Juan Daniel Vasconez:** A

**Francisco Gallegos:** entonces verás, eh,

**Juan Daniel Vasconez:** ver.

**Francisco Gallegos:** KPI3, básicamente es sacar un

**Juan Daniel Vasconez:** Ah.

**Francisco Gallegos:** promedio de la de la escala entre el 1 al 5 de la variable, eh, ¿cómo se llama? de por ya esa no es cierto.

**Juan Daniel Vasconez:** Sí, de rate. Ajá.

**Francisco Gallegos:** Entonces esa suponte aquí a ojo yo veo que

**Juan Daniel Vasconez:** Ya.

**Francisco Gallegos:** hay mucho más del muy útil, ¿no? 52 de de cuantadas

**Juan Daniel Vasconez:** Eh, 32 de 69\.

**Francisco Gallegos:** 32 de 69\. Entonces,

**Juan Daniel Vasconez:** Ajá.

**Francisco Gallegos:** más o menos un 40 y pico sabemos que debe ser puede ser que tengamos así como un puntaje de

**Juan Daniel Vasconez:** Sí,

**Francisco Gallegos:** 4.1

**Juan Daniel Vasconez:** tenía calculado en la anterior versión era como 3.7 así la

**Francisco Gallegos:** ya lo que sea.

**Juan Daniel Vasconez:** media.

**Francisco Gallegos:** Ese número ese va arriba ya tenemos el tres

**Juan Daniel Vasconez:** Ya,

**Francisco Gallegos:** cuatro.

**Juan Daniel Vasconez:** ya, pero perdimos un gráfico.

**Francisco Gallegos:** ¿Por qué?

**Juan Daniel Vasconez:** Lo dejamos en tres no más.

### **00:01:10** {#00:01:10}

**Francisco Gallegos:** ¿Por qué perdimos uno?

**Juan Daniel Vasconez:** Vamos a repetir

**Francisco Gallegos:** Pon los dos. Sí, sí, sí, sí.

**Juan Daniel Vasconez:** esto.

**Francisco Gallegos:** Es que uno es te doy el promedio y en el otro te digo el desglose.

**Juan Daniel Vasconez:** Okay,

**Francisco Gallegos:** Ya. Ajá. Entonces, van los dos.

**Juan Daniel Vasconez:** ya,

**Francisco Gallegos:** Uno es uno es el el el numerito en el KPI,

**Juan Daniel Vasconez:** ya,

**Francisco Gallegos:** el otro es del desglosado. Ya. Entonces, no importa. Ya. Entonces,

**Juan Daniel Vasconez:** okay.

**Francisco Gallegos:** tenemos tres. El número de gráfico se mantiene y nos queda una más.

**Juan Daniel Vasconez:** KPI.

**Francisco Gallegos:** Mm. Ya.

**Juan Daniel Vasconez:** Ajá.

**Francisco Gallegos:** Eh, a ver, ya sabemos cuántos mensajes mandaron. El número de mensajes que mandaron es incluso separándoles.

**Juan Daniel Vasconez:** Sí, es separándoles uno, o sea, ¿cuántos mensajes? Preguntas.

**Francisco Gallegos:** Ya.

**Juan Daniel Vasconez:** Podemos poner el número de conversaciones,

**Francisco Gallegos:** Ah, sí. Eso es bueno.

### **00:02:11** {#00:02:11}

**Juan Daniel Vasconez:** aunque es el mismo número de usuario, se supone, ¿no?

**Francisco Gallegos:** Solo hay una conversación por usuario. Claro, sí. No tiene sentido. No estamos midiendo diferentes.

**Juan Daniel Vasconez:** Ajá.

**Francisco Gallegos:** Ah, ya. Sabemos cuánta gente, sabemos cuánto están calificando el servicio. Sabemos cuál era el segundo.

**Juan Daniel Vasconez:** El segundo va a ser eh ¿Cuántas surveys han mandado?

**Francisco Gallegos:** Ya. Ajá. De hecho, ese puede ser el cuatro. Porque un poco va así, ¿cuánta gente más o menos, no?

**Juan Daniel Vasconez:** Okay.

**Francisco Gallegos:** ¿Cuánto volumen de de conversaciones generas? Luego tenemos un dos que está pendiente, luego tenemos un tres que te dice si es que esto sirve y finalmente cuánta gente te está respondiendo la encuesta. Ya. Entonces,

**Juan Daniel Vasconez:** Hm.

**Francisco Gallegos:** el KPI2 que nos toca definir puede ser algo como tiene que ser algo relacionado a la cantidad de gente, mensajes o algo así. Ah,

**Juan Daniel Vasconez:** Vamos a poner la media de mensajes por usuario.

**Francisco Gallegos:** es que ese ya en el gráfico se ve de una que es y es Ajá. El fund Sí. Eh, en el en el otro funcionaba porque es un promedio.

### **00:03:20**

**Juan Daniel Vasconez:** la

**Francisco Gallegos:** En este yo también había pensado en ese, el número promedio de mensajes, pero el funel ya responde y aparte muy pocos son más de dos. Eh, a ver, puede ser algo como, deja

**Juan Daniel Vasconez:** o sea,

**Francisco Gallegos:** ver.

**Juan Daniel Vasconez:** a largo plazo podríamos poner el tiempo usado eh tiempo promedio usado en en la encuesta. Aunque ahorita va a salir sesgado a julio, pero a largo plazo es un buen KPI, creo.

**Francisco Gallegos:** Y ese de las alertas solo tienes cuatro.

**Juan Daniel Vasconez:** Mhm.

**Francisco Gallegos:** Ya me pongo el nombre. Eh, sí, podemos sacar algún tiempo promedio de sesión.

**Juan Daniel Vasconez:** Si comparamos el created ad con El last message,

**Francisco Gallegos:** Ajá.

**Juan Daniel Vasconez:** sí, pero solo en julio.

**Francisco Gallegos:** Ya. Y en el registration

**Juan Daniel Vasconez:** Es si tenemos para todos,

**Francisco Gallegos:** completo.

**Juan Daniel Vasconez:** pero mira, eh, veamos laemp este tiene registration completed después de 45 segundos aquí.

**Francisco Gallegos:** Wow. Ya

**Juan Daniel Vasconez:** Y comparación acá es, mira, el created ad tiene

**Francisco Gallegos:** much

**Juan Daniel Vasconez:** 1355\. Okay. Ah, mira, el bot sube al Excel el usuario cuando termina todo, no cuando llega.

### **00:05:30** {#00:05:30}

**Francisco Gallegos:** hace mal. Bueno, sí cambian ahí los A ver, pensemos en otra número de temas. Vamosos poner algo así Oh. O ya, o sea, solo entrarle tres de estos, ¿no? Que se va de nos va a

**Juan Daniel Vasconez:** O sea,

**Francisco Gallegos:** descuadrar.

**Juan Daniel Vasconez:** sí por de sesión diciendo que el tiempo de sesión es este cuando llegaron y cuando acabaron esto.

**Francisco Gallegos:** Mhm.

**Juan Daniel Vasconez:** Pero mira, aquí son 45 segundos. Acá son, acá son 2 minutos, por ejemplo. Acá es un minuto, 3 minutos, 3 minutos.

**Francisco Gallegos:** Ya, ya, ya.

**Juan Daniel Vasconez:** Aquí son son 4 horas y media.

**Francisco Gallegos:** En serio. Ya. Sí. O sea,

**Juan Daniel Vasconez:** Ajá.

**Francisco Gallegos:** creo que va a funcionar, ¿no? Si tenemos completa casí.

**Juan Daniel Vasconez:** Estas sí están completas.

**Francisco Gallegos:** Sí, ya puede ser algo así como tiempo promedio de decisión. Eh, sí, está bueno

**Juan Daniel Vasconez:** H

**Francisco Gallegos:** eso. Ya completo dos ya. Jd el impacto no es mucho entonces, ¿sí o no?

### **00:07:23** {#00:07:23}

**Juan Daniel Vasconez:** al dashboard no al pipeline sí fue un poco grande. de por

**Francisco Gallegos:** chance, pero no tanto. Sí,

**Juan Daniel Vasconez:** eso.

**Francisco Gallegos:** ya. A ver, entonces verás, eh, martes, necesitamos mañana sí o sí acabar esto. ¿Cómo le ves?

**Juan Daniel Vasconez:** Sí, sí es viable.

**Francisco Gallegos:** Ya.

**Juan Daniel Vasconez:** O sea,

**Francisco Gallegos:** Em.

**Juan Daniel Vasconez:** yo espero hoy antes de acabar todo lo que acabar hoy ya tener de nuevo los exports listos y ya mañana sería solo hacer los gráficos y

**Francisco Gallegos:** Ya,

**Juan Daniel Vasconez:** terminar la última pestaña,

**Francisco Gallegos:** ya.

**Juan Daniel Vasconez:** que eso es mediod día. Ajá.

**Francisco Gallegos:** Ah, ese está con formato anterior, pero un verás.

**Juan Daniel Vasconez:** Sí, ya cuando entremos a este le

**Francisco Gallegos:** A ver, entonces eh fíjate que en el

**Juan Daniel Vasconez:** actualizo.

**Francisco Gallegos:** pipeline realmente es cambio de headers en algunas variables, ¿no? Cambio de orden en ciertas cosas,

**Juan Daniel Vasconez:** Mhm.

**Francisco Gallegos:** eh, pero de ahí el resto creo que sí funciona. La única excepción que tenemos que añadir para que no se nos rompa nada es en la parte de la categoría.

### **00:08:33** {#00:08:33}

**Juan Daniel Vasconez:** Ya.

**Francisco Gallegos:** Eh,

**Juan Daniel Vasconez:** Mhm.

**Francisco Gallegos:** como quedamos a partir de la última vamos a poner como sugerencias solo para que el análisis se vea bien y explicarles de por qué hicieron una estupidez,

**Juan Daniel Vasconez:** Mhm.

**Francisco Gallegos:** ya e está bueno mantenerla así. Entonces y de ahí no queda nada más. O sea, en datos es todo el impacto realmente que tuvieron Ya,

**Juan Daniel Vasconez:** Sí,

**Francisco Gallegos:** ya de una foto de E. Dale, entonces no debería tomar mucho el cloud o qué.

**Juan Daniel Vasconez:** eh. No, yo creo que ya está acabando. Ajá. O sea, tenía,

**Francisco Gallegos:** Ya.

**Juan Daniel Vasconez:** déjame ver cuántas tareas se puso para hacer todo esto después del prompt.

**Francisco Gallegos:** ¿Cuál fue el promo que le mandaste para esto?

**Juan Daniel Vasconez:** Ah, primero hicimos el análisis de la diferencia y acá está. Ah, y en base al análisis de la diferencia actualizamos esto. Acá está a 12 ahorita.

**Francisco Gallegos:** Pand.

**Juan Daniel Vasconez:** Ajá.

**Francisco Gallegos:** ¿Y qué modelo?

**Juan Daniel Vasconez:** Está con el mismo con el que iniciamos. Ajá.

### **00:09:42**

**Francisco Gallegos:** ¿Cuál era? Outs.

**Juan Daniel Vasconez:** Lopus. Ajá. 48\. Ajá.

**Francisco Gallegos:** Ya. Dale dale dale. Se apure.

**Juan Daniel Vasconez:** Sí,

**Francisco Gallegos:** Revísale JD cuando salga.

**Juan Daniel Vasconez:** sí,

**Francisco Gallegos:** que no que no haya hecho huevadas,

**Juan Daniel Vasconez:** sí, sí.

**Francisco Gallegos:** que le veo mandando full notas,

**Juan Daniel Vasconez:** Del like.

**Francisco Gallegos:** aunque capaz de sí porque pega en todas partes, pero bueno. E y fíjate que las reglas que definimos para ese campo en especial, eh, quede ya, porque si neces funcione. Ya,

**Juan Daniel Vasconez:** M.

**Francisco Gallegos:** ya, bro. Entonces, dale con eso. Ah, razones por las que nos metimos en esto es porque nos interesa eh quedar bien con estos mapas,

**Juan Daniel Vasconez:** Sí, sí,

**Francisco Gallegos:** ya porque generalmente esto no deberíamos haber tomado en tan poco tiempo,

**Juan Daniel Vasconez:** de acuerdo.

**Francisco Gallegos:** pero ya sabes cómo es esta nota. Eso, bro.

**Juan Daniel Vasconez:** Listo. De acuerdo,

**Francisco Gallegos:** Amigo,

**Juan Daniel Vasconez:** amigo. Adiós. Ya nos hablamos mañana. Chao. Igual. Co?

### **La transcripción finalizó después de 00:10:52**

*Esta transcripción editable se generó por computadora y puede contener errores. Los usuarios también pueden cambiar el texto después de que se cree.*