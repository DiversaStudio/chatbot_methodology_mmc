# **📝 Las notas**

jul 27, 2026

## **MMC Chatbot Methodology Checkpoint**

Invitado [Francisco Gallegos](mailto:francisco@diversa.studio) [Juan Daniel Vasconez](mailto:juanda@diversa.studio)

Archivos adjuntos [MMC Chatbot Methodology Checkpoint](https://calendar.google.com/calendar/event?eid=MzNrNDJnajU2aDAyMTdkNXR2aG0waHFxcjQganVhbmRhQGRpdmVyc2Euc3R1ZGlv)

Registros de la reunión [Transcripción](https://docs.google.com/document/d/1FAyoqHcoZv08Odzb4CJUm4bLbvRMO_Z_b6zMr04pyzo/edit?usp=drive_web&tab=t.dls7q7yi9pho) 

### **Resumen**

Revisión integral del diseño y consistencia visual para optimizar la estructura de datos en el tablero.

**Diseño y filtros estandarizados**  
Se decidió utilizar menús desplegables en lugar de elementos dispersos para optimizar espacio. Los filtros ahora priorizarán selectores de calendario sobre controles deslizantes redundantes.

**Estética y narrativa visual**  
Las tarjetas de indicadores clave de desempeño utilizarán bordes y sombras para evitar elementos flotantes. Se estableció priorizar el gráfico de usuarios activos con orientación vertical.

**Optimización del mapa y tablas**  
Se utilizará un tema oscuro para mapas geográficos y se simplificarán las tablas eliminando sombreados de filas. El conteo de mensajes se integrará directamente en los gráficos existentes.

### **Próximos pasos**

- [ ] \[Juan Daniel Vasconez\] Ajustar diseño de filtros: Convertir los filtros de multiopción a menús desplegables y utilizar selectores de calendario en lugar de barras deslizantes para mejorar la simetría. Asegurar que los títulos de los filtros sean de color gris y tengan una fuente más pequeña.

- [ ] \[Juan Daniel Vasconez\] Aplicar paleta de colores: Aplicar la paleta de colores oficial que incluye naranja y tonos crema. Diferenciar la barra lateral de filtros del resto del lienzo utilizando un tono verde más claro.

- [ ] \[Juan Daniel Vasconez\] Optimizar espaciado del dashboard: Incrementar el margen y la separación entre los diferentes plots para que el contenido respire mejor. Eliminar los subtítulos innecesarios dentro de los gráficos para optimizar el espacio disponible.

- [ ] \[Juan Daniel Vasconez\] Personalizar tarjetas KPI: Encerrar las tarjetas de indicadores en cajas con bordes discretos y sombras suaves. Esto permitirá distinguir visualmente los indicadores del resto del fondo blanco del canvas.

- [ ] \[Juan Daniel Vasconez\] Estandarizar títulos de gráficos: Revisar y corregir la redacción de todos los títulos en los gráficos del dashboard. Asegurar que el orden de los elementos siga una lógica de storytelling coherente para el usuario final.

- [ ] \[Juan Daniel Vasconez\] Configurar visualización de mapas: Cambiar el mapa base a gris y ajustar los parámetros de zoom automático. Investigar y cargar archivos de forma para representar correctamente los departamentos de Colombia en el mapa.

- [ ] \[Juan Daniel Vasconez\] Integrar mensajes en serie temporal: Integrar el conteo de mensajes a través del tiempo en el gráfico de usuarios activos usando un eje secundario. Asegurar que el filtro de categoría sea aplicado correctamente a este nuevo componente.

- [ ] \[Juan Daniel Vasconez\] Reestructurar segunda pestaña: Eliminar la columna de ciudades de la tabla principal en la segunda pestaña y convertirla en un filtro global. Reorganizar la vista para centralizar el análisis en categorías, instituciones y procedimientos.

- [ ] \[Juan Daniel Vasconez\] Implementar análisis: Organizar los gráficos de análisis en cuatro secciones. Disponer las comparativas de colores rojo y verde en la parte superior e inferior.

- [ ] \[Juan Daniel Vasconez\] Añadir dona: Integrar el análisis de calificación de utilidad en un gráfico de dona. Cruzar esta información con la variable de recomendación usando claves de color.

- [ ] \[Juan Daniel Vasconez\] Evaluar gráficos: Probar alternativas de visualización entre barras verticales y treemap para medir el compromiso. Seleccionar la opción que mejor represente la información.

- [ ] \[Juan Daniel Vasconez\] Configurar filtros: Determinar qué filtros de ciudad y categoría resultan más pertinentes para los tableros. Implementar estas opciones para facilitar el análisis profundo.

- [ ] \[Juan Daniel Vasconez\] Formatear dashboard: Aplicar un estilo uniforme en todos los elementos visuales. Estandarizar cajitas, sombras, márgenes y colores de títulos.

- [ ] \[Juan Daniel Vasconez\] Incorporar feedback: Implementar las observaciones recibidas en la primera pestaña y en la sección de experiencia de demanda. Preparar los cambios para el siguiente checkpoint.

### **Detalles**

* **Diseño de Logos y Menús de Filtros**: Francisco Gallegos y Juan Daniel Vasconez analizan la disposición de los logos en la parte superior y la necesidad de estandarizar los menús de filtros. Acuerdan utilizar cajas de selección (menús desplegables) en lugar de elementos dispersos para optimizar el espacio y mejorar la organización visual ([00:00:00](#00:00:00)).

* **Consistencia en los Filtros**: Se discute la necesidad de unificar la apariencia de los filtros en todo el tablero. Acuerdan eliminar los controles deslizantes de fecha y las opciones redundantes para priorizar los selectores de calendario, asegurando que todos los filtros tengan un diseño y fuente consistentes ([00:02:12](#00:02:12)).

* **Paleta de Colores y Espaciado**: Francisco Gallegos sugiere aplicar un color de fondo diferenciado en la barra lateral para separar visualmente los filtros de los gráficos. Confirman el uso de la paleta de colores de "Mix Migration", con énfasis en el contraste del naranja, y acuerdan aumentar el espacio en blanco (márgenes) entre los gráficos para una mejor legibilidad ([00:04:48](#00:04:48)).

* **Estilo de las Tarjetas de KPIs**: Para evitar la apariencia de que los gráficos "flotan" sobre el fondo blanco, Francisco Gallegos propone encerrar las tarjetas de indicadores clave de desempeño (KPIs) en cajas con bordes sutiles y sombras. También sugieren eliminar notas de pie de página innecesarias para ganar espacio en el lienzo ([00:07:03](#00:07:03)).

* **Lógica Narrativa y Orientación de Gráficos**: Francisco Gallegos enfatiza la importancia de una estructura lógica que cuente una historia con los datos. Deciden priorizar el gráfico de usuarios activos ("Active Users") al inicio y cambiar los gráficos de barras de orientación horizontal a vertical para evitar repeticiones visuales ([00:09:27](#00:09:27)).

* **Visualización del Mapa y Fondos**: Exploran opciones para el mapa geográfico, decidiendo usar un tema oscuro ("Dark") y habilitar el auto-zoom para centrarse en los datos. Acuerdan que la limpieza visual es prioritaria y deciden no saturar el mapa con etiquetas si el espacio es limitado ([00:13:27](#00:13:27)).

* **Gestión de Datos Geográficos**: Discuten si usar shapefiles o coordenadas de latitud/longitud para el mapa de Colombia. Concluyen que el enfoque actual de usar puntos basados en la ubicación de ciudades es suficiente y efectivo para mantener la funcionalidad del tablero sin complicar el proceso de carga de datos ([00:22:40](#00:22:40)).

* **Ajustes Finales de Controles del Mapa**: Se acuerda limpiar la interfaz del mapa eliminando elementos de selección innecesarios (como el lazo) y ajustando los paddings para que el gráfico se vea lleno y profesional desde la apertura del informe ([00:29:57](#00:29:57)).

* **Estructura de la Pestaña de Experiencia de Demanda**: Analizan la segunda pestaña enfocada en instituciones y procedimientos. Identifican que el gráfico de series de tiempo de mensajes está saturado y deciden integrar el conteo de mensajes directamente en el gráfico de "Active Users" mediante un eje Y secundario, lo que permitirá eliminar el gráfico redundante ([00:32:47](#00:32:47)).

* **Conectividad de Filtros**: Confirman que todos los gráficos y las tarjetas de KPIs deben estar correctamente conectados a los filtros de selección (como ciudades) para asegurar que la interactividad refleje los datos de manera precisa en toda la página ([00:37:30](#00:37:30)).

* **Formato de Tablas**: Para mejorar la legibilidad de las tablas, acuerdan eliminar el sombreado gris de las filas y utilizar fuentes en negrita o de mayor tamaño para los encabezados, logrando un aspecto más limpio y formal ([00:40:30](#00:40:30)).

* **Distribución Final de Gráficos en la Segunda Pestaña**: Definen que la segunda pestaña debe centrarse en tres análisis principales: categorías, instituciones y procedimientos. Proponen usar gráficos de dona para medir las calificaciones de utilidad y gráficos de barras verticales para el engagement, maximizando el espacio disponible ([00:42:10](#00:42:10)).

* **Cierre y Próximos Pasos**: Francisco Gallegos y Juan Daniel Vasconez concluyen que la prioridad actual es aplicar la consistencia visual (cajas, márgenes, colores) en todas las pestañas. Acuerdan coordinar un próximo punto de control para revisar los cambios implementados ([00:53:30](#00:53:30)).

*Revisa las notas de Gemini para asegurarte de que sean precisas. [Obtén sugerencias y descubre cómo Gemini toma notas](https://support.google.com/meet/answer/14754931)*

*Cómo es la calidad de **estas notas específicas?** [Responde una breve encuesta](https://google.qualtrics.com/jfe/form/SV_5bXzKQfylMIhSXc?confid=bIBlE84ZpHkEy9IiM3s_DxIYOAIIigIgABgBCA&detailid=standard&screenshot=false&entryPoint=footerMain&isGoogler=False) para darnos tu opinión; por ejemplo, cuán útiles te resultaron las notas.*

# **📖 Transcripción**

jul 27, 2026

## **MMC Chatbot Methodology Checkpoint \- Transcripción**

### **00:00:00** {#00:00:00}

**Juan Daniel Vasconez:** Ya,

**Francisco Gallegos:** Ya. Bueno, entonces,

**Juan Daniel Vasconez:** ahí empezó.

**Francisco Gallegos:** a ver, primero eh los logos en blanco, los dos en la esquina,

**Juan Daniel Vasconez:** Ok.

**Francisco Gallegos:** ¿no? Eh, fíjate que el espacio esté igual que en la portada. Ahora creo que podemos reducirle un poquito la la franja verde para darnos más espacio en eso. Ya luego, gracias. Eh,

**Juan Daniel Vasconez:** Mhm.

**Francisco Gallegos:** necesitamos que, por ejemplo, todas estas que sean selecciones de filtro de multiopción estén en cajas, ¿ya?, o sea, en en menús desplegables.

**Juan Daniel Vasconez:** Okay.

**Francisco Gallegos:** Eso lo puedes editar ahí mismo, ¿verdadas? En el drill throw mirarle atrás.

**Juan Daniel Vasconez:** ¿En dónde? Perdón.

**Francisco Gallegos:** Ponle ahí.

**Juan Daniel Vasconez:** A ver, acá.

**Francisco Gallegos:** Ajá. Drill throw.

**Juan Daniel Vasconez:** Ah,

**Francisco Gallegos:** No, no está bien.

**Juan Daniel Vasconez:** aquí.

**Francisco Gallegos:** Entonces, ándate al otro el edit drop.

**Juan Daniel Vasconez:** Drop down.

**Francisco Gallegos:** Ya. Ajá. Entonces, tienes el dropdown y ahora otra cosa es

### **00:01:06**

**Juan Daniel Vasconez:** Yeah.

**Francisco Gallegos:** ah el texto de adentro está grandotote, ¿ya? Y los textos en general están diferentes, ¿sabes? Ah,

**Juan Daniel Vasconez:** Sí,

**Francisco Gallegos:** necesitamos.

**Juan Daniel Vasconez:** es que no acá no les tenía el dropdown. Ajá.

**Francisco Gallegos:** Ajá. Sí.

**Juan Daniel Vasconez:** Y no me entraban todos.

**Francisco Gallegos:** Eh,

**Juan Daniel Vasconez:** Sí,

**Francisco Gallegos:** sí,

**Juan Daniel Vasconez:** se de

**Francisco Gallegos:** sí, pero en general, mira, lo que se suele hacer para que quede bien la barra lateral de

**Juan Daniel Vasconez:** un

**Francisco Gallegos:** filtros es uno utilizar un color que sea diferente al de los títulos que vemos en los plots, ¿ya? Otro es ponerle toda una barra de un color a toda la barra lateral, ¿ya? Que puede ser un verdecito más bajo, ¿ya? Un así como medio medio medio no que no se note que es blanco. Ya. Para que se diferencie que por un lado tienes eh la sección de

**Juan Daniel Vasconez:** Ya.

**Francisco Gallegos:** filtros y por otro lado tienes los plots, ¿ya? Eh,

**Juan Daniel Vasconez:** Mhm.

**Francisco Gallegos:** que se haga esa diferencia.

### **00:02:12** {#00:02:12}

**Francisco Gallegos:** Ya. Luego, eh, fíjate que, por ejemplo, hm, por ejemplo, esta está sí está útil ese digamos filtro de fechas,

**Juan Daniel Vasconez:** No.

**Francisco Gallegos:** pero se ve muy grande las bolas, ¿ya? Entonces como que resalta innecesariamente eh, y solo es un filtro. Ya. Otra cosa que puede quedar es intenta que todos los filtros se vean igual. ¿Y cómo hacemos que se vean igual? Por ejemplo, aquí eh abajo tienes una un dropdown con cajas, arriba tienes unas bolitas para selectar el range, ¿ya? Entonces,

**Juan Daniel Vasconez:** Mhm.

**Francisco Gallegos:** pero también tenemos esas cajas donde tú puedes seleccionar el rango en un calendario. Entonces, digamos, más simétrico se ve si es que solo le dejamos los lectores de calendario y le volamos el slider es ya. Eh, ajá.

**Juan Daniel Vasconez:** Ya.

**Francisco Gallegos:** E sí, creo que le puedes la opción es quitarle y no ocultarle. E,

**Juan Daniel Vasconez:** Eh,

**Francisco Gallegos:** ajá,

**Juan Daniel Vasconez:** déjame ver porque no justo está buscando cómo quitarle,

**Francisco Gallegos:** sí,

**Juan Daniel Vasconez:** pero no le veo. Ah, ya.

**Francisco Gallegos:** sí.

### **00:03:21**

**Francisco Gallegos:** ¿Ya? Entonces, eh, mira, ahora otra cosa que ahí sí se nota. Por ejemplo, el tamaño de la letra que está dentro de la caja del del dropdown está más grande que incluso el título de la A. Entonces,

**Juan Daniel Vasconez:** M.

**Francisco Gallegos:** más que sean más chiquitos, utiliza un color un poco gris para el título de los filtros. Ya. Eh, atrás la sección que tenga un color diferente al canvas principal del del dashboard. Ya, esto por el lado de filtros aplica para todas,

**Juan Daniel Vasconez:** Ya.

**Francisco Gallegos:** ¿ya? Eh, entonces, por ejemplo, te va a quedar en algunas pestañas más filtros que en otras. Ya. Eh,

**Juan Daniel Vasconez:** Sí.

**Francisco Gallegos:** ahora lo conveniente es uno, que si vas a, digamos, tener eh algunos filtros eh que se comparten estén en el mismo orden, ¿ya? Y que funcionen de la misma forma. Entonces, e que se algunos tengas más en algunos otros, pero que vayan un poco ahí eh con consistencia. Ya. Eh, eso por el lado de los filtros. Ahora verás, e creo que podemos o el tema de los colores ya está acabado o aú no.

**Juan Daniel Vasconez:** Eh, los colores sí, o sea, sí sé cuáles son los colores de Mix Migration y sí tengo la

### **00:04:48** {#00:04:48}

**Francisco Gallegos:** Ya,

**Juan Daniel Vasconez:** paleta.

**Francisco Gallegos:** ponte en el primero, ese naranja y ese y ese medio como cremita, perdón, en la segunda, en ese gráfico de barras. Esos son colores de

**Juan Daniel Vasconez:** Eh, este naranja no, pero lo que estaba viendo acá, mira, sí usan este cremita aquí,

**Francisco Gallegos:** Ya,

**Juan Daniel Vasconez:** por ejemplo.

**Francisco Gallegos:** ya. Ah, ya. Bacana. Ya,

**Juan Daniel Vasconez:** Ajá. Un verde.

**Francisco Gallegos:** ya.

**Juan Daniel Vasconez:** Pensaba ponerle como que un verde más clarito,

**Francisco Gallegos:** Sí,

**Juan Daniel Vasconez:** tal vez.

**Francisco Gallegos:** sí, ya. Bacán. Eh,

**Juan Daniel Vasconez:** Ajá.

**Francisco Gallegos:** fíjate en la en la en la paleta, ¿ya? Eh, porque ahí si hay un contraste super heavy, es el naranja.

**Juan Daniel Vasconez:** Ya me puedo poner de una vez.

**Francisco Gallegos:** Se llama la atención.

**Juan Daniel Vasconez:** Déjame

**Francisco Gallegos:** Ya. Ahora, otra cosa, bro. verás,

**Juan Daniel Vasconez:** ver.

**Francisco Gallegos:** eh, ponte en el pon. Dale, dale. Si quieres

### **00:05:35**

**Juan Daniel Vasconez:** Voy.

**Francisco Gallegos:** acabar.

**Juan Daniel Vasconez:** Mm. No me encanta. Bueno, entonces en el siguiente

**Francisco Gallegos:** Ya, ya.

**Juan Daniel Vasconez:** Sí.

**Francisco Gallegos:** Entonces verás ahí mismo. Otra cosa. Verás, necesitas mejorar el espacio entre los plots y y los

**Juan Daniel Vasconez:** Mhm.

**Francisco Gallegos:** márgenes entre ellos como que dale más espacio porque mira, solo son cuatro grafricotes, entonces tenemos el espacio suficiente para darle una separación bacán, ¿no? Mira, el la barra de filtros generalmente ya es como que te tiene que ocupar, qué sé yo, quizá un séptimo del del ancho, ¿no? No le puedes hacer tan flaquitos tampoco. E ya, pero lo que sí es,

**Juan Daniel Vasconez:** Yeah.

**Francisco Gallegos:** por ejemplo, eh el active users y el mapa casi se topan, si es que no se están topando. El users by city duration canon. Abajo tienes la leyenda seguidito y abajo el gráfico le

**Juan Daniel Vasconez:** Mhm.

**Francisco Gallegos:** hace le hace que estén muchos elementos. Incluso te diría, no hace falta que haya una leyenda de de color porque la el mismo eje ya te ya te ya te hace. Ajá.

### **00:07:03** {#00:07:03}

**Francisco Gallegos:** Entonces, mira, ahí le limpiaste full.

**Juan Daniel Vasconez:** Yep.

**Francisco Gallegos:** Eh, ya. Ahora eso para todos. Eh, busca cómo separar un poquito más. Eh, mira, aquí no hace falta poner este de P 154 Active users porque eh el dashboard es para que pongan el mouse y digan, "¿Y cuánto fue?" Ya, eso fue.

**Juan Daniel Vasconez:** rápido.

**Francisco Gallegos:** Entonces bórrale esa nota e esa nota chiquita como subtítulo que tienes y eso nos va a dar un poquito más de espacio.

**Juan Daniel Vasconez:** Yep.

**Francisco Gallegos:** Eh, igual eh le puedes ir separando un poco más del título al al plot. Ya. Y otra cosa, bro, es verás. Ah,

**Juan Daniel Vasconez:** Yep.

**Francisco Gallegos:** todos los gráficos es como que tienen fondo blanco, ¿ya?

**Juan Daniel Vasconez:** Mhm.

**Francisco Gallegos:** E el canvas en general donde están los plots es blanco,

**Juan Daniel Vasconez:** Aha.

**Francisco Gallegos:** entonces parece que todo está volando. E sugerencias para mejorar esto. Eh, por es por ejemplo,

**Juan Daniel Vasconez:** Ok.

**Francisco Gallegos:** la parte de los KPIs de las tarjetas les puedes poner un color diferente, ya para que se vean que son tarjetitos, ya un verdecito, no sé, algo.

### **00:08:13**

**Francisco Gallegos:** Pruébale. Ya. Otro. eh encerrarles en cajitas con un borde muy este eh así discreto, bajito y ponerle quizá una sombrita para que se note que son cuatro gráficos. Ya. Entonces, dale más espacio, eh, eso para todos los plots incluso, ¿no? E deses más espacio entre títulos y plots, ¿ya? O más márgenes, separación entre plots en sí, ¿ya? y e los bordes y el 3D para que se note la diferencia.

**Juan Daniel Vasconez:** Yeah.

**Francisco Gallegos:** Ah, entonces sugerencia para eso es e dale al

**Juan Daniel Vasconez:** Ah.

**Francisco Gallegos:** Eh, Gemini, al Google, al Cloud, perdón, al Cloud, al que sea. E estoy haciendo este dashboard,

**Juan Daniel Vasconez:** Sí,

**Francisco Gallegos:** mira. Ajá. Ahí está. Como que un poco Sí,

**Juan Daniel Vasconez:** sí, justo ese fue el que dijo la di que le

**Francisco Gallegos:** algo así como para que no se note que estén ahí flotando.

**Juan Daniel Vasconez:** gustó.

**Francisco Gallegos:** Un poco tenerle de esa forma. Ya. E eso, brother. De ahí el resto estaba acá en el contenido es lo que importa, pero ya sabes que aquí también es el el look.

### **00:09:27** {#00:09:27}

**Juan Daniel Vasconez:** Mhm. Aquí ahora que le hicimos esto,

**Francisco Gallegos:** Ajá.

**Juan Daniel Vasconez:** se me ocurre mover mover 2 KP para acá y a esto hacerle

**Francisco Gallegos:** No, jamás.

**Juan Daniel Vasconez:** para como que un poco más

**Francisco Gallegos:** Mm. Sí, sí te cacho. Este sí te cacho,

**Juan Daniel Vasconez:** grande.

**Francisco Gallegos:** pero no. Eh, ¿por qué

**Juan Daniel Vasconez:** ¿Por qué estamos perdiendo aquí espacio?

**Francisco Gallegos:** el problema es que siempre tiene que ir así un estándar o verás otra cosa? Ya. Eh, no, no, no es preferible mejor tener los filtros a la al lado, ¿ya? Em,

**Juan Daniel Vasconez:** Yep.

**Francisco Gallegos:** este es, digamos, como que el que resume el edad, ¿no es cierto?

**Juan Daniel Vasconez:** Sí.

**Francisco Gallegos:** Ya. Verás, primero el where Sami Riches and users by City dice lo mismo, ¿no es cierto?

**Juan Daniel Vasconez:** Mm. No, este este título está mal. Ajá.

**Francisco Gallegos:** Ah, ya. Okay. Ya, eso

**Juan Daniel Vasconez:** Sería claro.

**Francisco Gallegos:** es

**Juan Daniel Vasconez:** Ah, algo así.

### **00:10:53**

**Francisco Gallegos:** permanencia por usuarios. No,

**Juan Daniel Vasconez:** Sería

**Francisco Gallegos:** permanencia. No creo que el título estaba revis que esté bien redactado, pero sigo. Ya. Entonces verás,

**Juan Daniel Vasconez:** sí.

**Francisco Gallegos:** e inviértele las el ponles verticales, no horizontales a esas barras, porque arriba ya tenemos el mismo gráfico, entonces se ve un poco repetido. Ajá. Ya. Bacán. E ahora eh verás uno el los dashboards igual imagínate que en el orden en que tú vas viendo y te vas como que cachando los gráficos también tiene que tener

**Juan Daniel Vasconez:** Mhm.

**Francisco Gallegos:** cierto como que sentido, cierta lógica, cierto storytelling incluso. Ya. Entonces, verás, Sami, user profile,

**Juan Daniel Vasconez:** Mhm.

**Francisco Gallegos:** básicamente lo que nos interesa es saber cuántos, en dónde y un poco cómo son, ¿ya? Entonces,

**Juan Daniel Vasconez:** Hm.

**Francisco Gallegos:** si es que tú piensas en esa primera pregunta, lo primero que deberíamos ver son los active users, ¿sí o No,

**Juan Daniel Vasconez:** Sí,

**Francisco Gallegos:** entonces este

**Juan Daniel Vasconez:** o sea,

**Francisco Gallegos:** Simón

**Juan Daniel Vasconez:** es ahorita el orden de los de los gráficos le puse igual que en el requirements, según el orden que justo.

### **00:12:07**

**Francisco Gallegos:** ya sí ahorita eh piensa que un poco no tiene que estar tan igual, sino más bien como que ponte en el sombrero del Simón, ¿ya? Entonces, imagínate que el Simón o alguien que toma decisiones o algo por el estilo dice, este, necesito, por ejemplo, si es que a él le califican, a él los equipos, le califican con hermanito, necesitamos saber cuántas personas activas están en tu chatbot o o o cerramos los fondos para eso. Entonces, tú dices, "No, mira, si está en un promedio de todo, yo tengo al menos unos más allá de 100 usuarios. Ya. Active users, primer gráfico que ves. ¡Uf\! Ya. Eh, entonces, ah, eso está buenísimo. Luego tienes los KPIs arriba super geniales que ya te dicen full cosas, ¿ya? Eh, entonces yo yo creo que está bien así, mira. Active users, luego mapa, ya, luego abajo del active los permanency by users, ya que creo que ese título hay que darle un ojo. Y el users by regender,

**Juan Daniel Vasconez:** Sí,

**Francisco Gallegos:** eh, hay que mejorar ese título igual.

**Juan Daniel Vasconez:** es que los títulos están según los loss, entonces no limpio

**Francisco Gallegos:** Ajá.

### **00:13:27** {#00:13:27}

**Francisco Gallegos:** Ya. Bacán. Entonces,

**Juan Daniel Vasconez:** Aha.

**Francisco Gallegos:** e sí. Ya, mira, ahí tienes un gráfico que correlaciona dos variables. Tienes KP, tienes geografía, tienes eso y ya. Entonces, e ahora, bro, el único cambio es darle más espacio. Ya necesitamos que respire, darle un poquito más de de eso. Em el mapa puedes cambiarle el el basem map.

**Juan Daniel Vasconez:** Sí, déjame ver. Hay este, hay este, hay este, hay este y hay este.

**Francisco Gallegos:** ¿Cuál te gustó? Sí, sí.

**Juan Daniel Vasconez:** M, a mí personalmente me gusta este, creo, como que pega más. O tal vez hasta este es un poquito más

**Francisco Gallegos:** Ah, sí,

**Juan Daniel Vasconez:** claro.

**Francisco Gallegos:** creo que el primero que que dijiste personalmente, la EAL está una bestia. Ya. E ahora hay como por ejemplo ah no, no sabes no está llenando de letras de esa nota.

**Juan Daniel Vasconez:** Se puede quitar las levels,

**Francisco Gallegos:** Ah,

**Juan Daniel Vasconez:** si no

**Francisco Gallegos:** pero le puedes prender el en los móvulses que sí se vea.

**Juan Daniel Vasconez:** eh creo que no.

### **00:14:56**

**Francisco Gallegos:** Abajo está. Mira,

**Juan Daniel Vasconez:** Baja,

**Francisco Gallegos:** Pon auto. Déjalo en auto. Sí.

**Juan Daniel Vasconez:** Ah.

**Francisco Gallegos:** Y y no le pongas \-10. Ponlo un poquito más grande para que se vea. Ah, mucho, creo. Debe ser gigantesco. Pon en un Yo creo que en un 10 ya. Y no sabes, está no está mostrando muchas las ciudades,

**Juan Daniel Vasconez:** Claro,

**Francisco Gallegos:** ¿eh?

**Juan Daniel Vasconez:** tocaría ser así porque no da el chance

**Francisco Gallegos:** Y en category label ahí no

**Juan Daniel Vasconez:** de que seas los bowers. Ajá.

**Francisco Gallegos:** préndele. Ah, maldición. Sol. Ah, pero si le puedes escoger cuál es en

**Juan Daniel Vasconez:** Mm.

**Francisco Gallegos:** values.

**Juan Daniel Vasconez:** Déjame ver. Este es en el Tultip.

**Francisco Gallegos:** Ah,

**Juan Daniel Vasconez:** Ajá.

**Francisco Gallegos:** sí, en el tool tip. Ahí debería estar el el la zoom o el count o qué campo es.

**Juan Daniel Vasconez:** Cicano, este es el nombre, el el nombre canonizado.

### **00:16:13**

**Francisco Gallegos:** Ay, ábrele.

**Juan Daniel Vasconez:** Ajá.

**Francisco Gallegos:** Está cogiendo de cuál de DM City.

**Juan Daniel Vasconez:** Sí.

**Francisco Gallegos:** Ábrele.

**Juan Daniel Vasconez:** Cic. A ver,

**Francisco Gallegos:** Ah,

**Juan Daniel Vasconez:** espericano.

**Francisco Gallegos:** ya. Ah, wow. Pero, ¿y dónde están los conteos?

**Juan Daniel Vasconez:** Estas vienen de otra parte, estas vienen de de los usuarios, que es una medida.

**Francisco Gallegos:** Ah, ya, ya. Ya. Entonces, Google es. Ah, entonces ahí en el tool tip no deberías ponerle el

**Juan Daniel Vasconez:** ¿Cuál?

**Francisco Gallegos:** otro, el el mismo el users zoom of users. No puedes ponerle. Ponle está prendido. Ahora ponte en el gráfico.

**Juan Daniel Vasconez:** Sí, es muy gráfica.

**Francisco Gallegos:** Ahí hay category labels. Hit, no el category labels. Préndele. Sigue cogiendo las son las categorías.

**Juan Daniel Vasconez:** La t

**Francisco Gallegos:** Ah, y cuando le pasas la el el mouse,

**Juan Daniel Vasconez:** loitó.

**Francisco Gallegos:** apágale el category labels. ¿Qué tienes?

### **00:17:52**

**Francisco Gallegos:** Todo users.

**Juan Daniel Vasconez:** No sale la latitud de la longitud.

**Francisco Gallegos:** Users dos veces.

**Juan Daniel Vasconez:** Aha.

**Francisco Gallegos:** Entonces, Ponle, ponle n más como estaba antes. JD estaba bien. Ya. El el basem creo que no nos funciona. Ponle otro.

**Juan Daniel Vasconez:** Cuando le pongo el más, ahí sí sale Santa Marta.

**Francisco Gallegos:** Está bien así. A ver, ponle otro basem map. Light. Ya. Y antes le tenías prendido, ¿qué le qué le tenías prendido? Otros tenías, ¿no? En el map settings estaba.

**Juan Daniel Vasconez:** Déjame,

**Francisco Gallegos:** Ah, show label ahí.

**Juan Daniel Vasconez:** me acuerdo

**Francisco Gallegos:** Show. Ah, no, no te sale nada.

**Juan Daniel Vasconez:** Aha.

**Francisco Gallegos:** ¿Cuál?

**Juan Daniel Vasconez:** A menos de que no sé, tal vez con otro tipo de mapa sirva mejor con un o algo así.

**Francisco Gallegos:** ¿Cuál? ¿Cuál tú tienes? Ah, sí. Shape, F map.

**Juan Daniel Vasconez:** Hay uno con Jis, pero no

**Francisco Gallegos:** No, no,

**Juan Daniel Vasconez:** recuerdo

### **00:19:16**

**Francisco Gallegos:** no nos darnos una vueltota. Este,

**Juan Daniel Vasconez:** porque ver vamos a probar con este tal vez. No, este no tampoco.

**Francisco Gallegos:** a ver, otra base. ¿Qué es eso?

**Juan Daniel Vasconez:** Este, tal vez

**Francisco Gallegos:** Nombre el Grey. El Grey es el que estaba,

**Juan Daniel Vasconez:** agre el que estaba.

**Francisco Gallegos:** ¿no?

**Juan Daniel Vasconez:** Ajá.

**Francisco Gallegos:** el dark. Ahora en Bobles, ¿qué qué sale? Puedes abrir el

**Juan Daniel Vasconez:** Solo sale el scaling, los colores y el tamaño.

**Francisco Gallegos:** y ya y ponte general al lado y effects tienes

**Juan Daniel Vasconez:** sobre, o sea,

**Francisco Gallegos:** plataforma y

**Juan Daniel Vasconez:** ese general del cuadrado del

**Francisco Gallegos:** ya tex y en los tres puntitos que había. Ah, no hay nada. Ya. Eh, déjale con el dark ahora.

**Juan Daniel Vasconez:** Yeah.

**Francisco Gallegos:** Seguro no hay cómo ponerle los números en las bolas. Ah, y otra cosa, eh, cuando tú por default le abres, ¿en qué zoom se queda? No, no,

**Juan Daniel Vasconez:** Ahí.

**Francisco Gallegos:** pero, o sea, por ejemplo, cuando abres por primera vez el reporte el el Power

### **00:21:17**

**Juan Daniel Vasconez:** Ah. Ahí.

**Francisco Gallegos:** BI,

**Juan Daniel Vasconez:** Ajá. Justo así.

**Francisco Gallegos:** pero y eso cómo se fija automáticamente, ¿dónde están los datos o cómo?

**Juan Daniel Vasconez:** Eh, claro, se fija automáticamente de la concentración de los

**Francisco Gallegos:** Ah,

**Juan Daniel Vasconez:** datos.

**Francisco Gallegos:** ya ya ya ya. Okay. Ya. Ese del también quítale los títulos. Sí, darás un un ojo acá. Yo creo que ya no pega mucho eso de de ser medios poéticos en los títulos, ¿no? Tipo eh ciudades cubiertas o algo así, no sé. Ya. A ver. Ya. Listo, bro. Entonces, e con esos con esos puntos creo que tienes completo e la la primera la primera pestaña. Si quieres vamos de la segunda, no sé si tienes algo adicional sobre esto,

**Juan Daniel Vasconez:** esta no.

**Francisco Gallegos:** amigo.

**Juan Daniel Vasconez:** O sea, estoy pensando cómo hacer los tamaños mismo para que se vea bien, porque hasta ahorita creo que están chiquitos

**Francisco Gallegos:** Ya.

**Juan Daniel Vasconez:** igual.

**Francisco Gallegos:** e como chiquitos los gráficos.

**Juan Daniel Vasconez:** Ajá.

### **00:22:40** {#00:22:40}

**Francisco Gallegos:** Eso es lo que alcanzan.

**Juan Daniel Vasconez:** Esta

**Francisco Gallegos:** Están bien. Ahora verás, eh, suponte cuál es el tamaño de la de la hoja esta.

**Juan Daniel Vasconez:** es la de la 169 de 1920 por

**Francisco Gallegos:** Ya. Sí,

**Juan Daniel Vasconez:** 720\.

**Francisco Gallegos:** porque es, mira, este es el tamaño que generalmente causa bien en una laptop, ¿ya? E entonces ahora quizás dejarle el mapa abajo, tipo active permanency users y al último el el el el mapa. Ahí puede ser. Eh, le puedes dar un poco más de margen y en este no le puedes poner leyenda, ¿no?

**Juan Daniel Vasconez:** H no es que el problema es que esto si es que esto eh me fijara los puntos por poner Yeah. el nombre de la ciudad podría poner como que el nombrecito, pero no no es por ahí.

**Francisco Gallegos:** Ahora y ese que el mapa, el otro que se llama El sh map.

**Juan Daniel Vasconez:** Ben

**Francisco Gallegos:** ¿Qué hacemos? ¿Qué hacemos, bro? Le puedes poner gris otra vez.

**Juan Daniel Vasconez:** o se podríamos poner algo así para Colombia, pero no sé cómo moverle porque esto es de Estados Unidos.

### **00:24:38**

**Francisco Gallegos:** Ábrele, por si. ¿Cuál es el

**Juan Daniel Vasconez:** Custom supong, pero hay que subir el mapa.

**Francisco Gallegos:** y no hay no te sale colombiar y en type solo

**Juan Daniel Vasconez:** No,

**Francisco Gallegos:** hay arriba el no arito la primera

**Juan Daniel Vasconez:** perdón, aquí. Ah,

**Francisco Gallegos:** Ponle por ahí,

**Juan Daniel Vasconez:** URL.

**Francisco Gallegos:** pone un URL shape Colombia Provinces. Está a nivel de provincia,

**Juan Daniel Vasconez:** Ajá.

**Francisco Gallegos:** ¿no? Sí. A ver, te ayudo a buscar algunas. H

**Juan Daniel Vasconez:** Estoy Ah, pero mira, está bien.

**Francisco Gallegos:** se teorizó.

**Juan Daniel Vasconez:** Mir, esto encontré en

**Francisco Gallegos:** Ah, no es nivel creo que p\*\*\*

**Juan Daniel Vasconez:** GF

**Francisco Gallegos:** barrio.

**Juan Daniel Vasconez:** departamentos médicos población estos departamentos así. Mira, intentemos con

**Francisco Gallegos:** Našal.

**Juan Daniel Vasconez:** este. Mira ahí,

**Francisco Gallegos:** A ver y a ver,

**Juan Daniel Vasconez:** pero se vería así.

**Francisco Gallegos:** ponle las Ya. No.

**Juan Daniel Vasconez:** pero no sabría cómo usarlo. Déjame ver.

### **00:27:01**

**Francisco Gallegos:** Está bien así. La proyección no es data format, o sea, verás, lo único que necesitas es tener una tabla de correspondencia entre la latitud y longitud y el polígono al que corresponde eso.

**Juan Daniel Vasconez:** Aha.

**Francisco Gallegos:** Ajá. Eh, y ahí sí podemos pintarle de verde. Creo que va a quedar mejor. Visualmente se ve más limpio.

**Juan Daniel Vasconez:** Ya,

**Francisco Gallegos:** En todo caso se ve superlmpio. Ya. Entonces,

**Juan Daniel Vasconez:** ya.

**Francisco Gallegos:** eh sí es un cambio un poco medio chiquito. Ya preferible JD si es que le cargamos nosotros el el SH file. Ya búscate el SH file a nivel eh subnacional de Colombia.

**Juan Daniel Vasconez:** Yeah.

**Francisco Gallegos:** Ah, o sea, a nivel de provincia, que creo que es la, imagínate, la primera agregación que existe ya después de a nivel país. Eh, nosotros tenemos así los datos o tenemos a nivel de ciudad.

**Juan Daniel Vasconez:** Ciudad. Aha.

**Francisco Gallegos:** Ciudad. Es que mira, una cosa es luego cómo se pintan la ciudad. Ya es un territorio gigante y nos va a quedar solo unas ciudades chiquitas.

### **00:28:19**

**Francisco Gallegos:** Eh, pintaditas. Lo que podemos hacer es esto

**Juan Daniel Vasconez:** A

**Francisco Gallegos:** correspondencia en tres niveles, latitud, longitud con la ciudad y la ciudad con la provincia a la que pertenece o departamentos se llaman en Colombia. Eh, para que nos pinte en este departamento tantos que corresponde esta ciudad.

**Juan Daniel Vasconez:** O sea, como podemos hacerle justo como lo tenemos

**Francisco Gallegos:** Ah,

**Juan Daniel Vasconez:** acá,

**Francisco Gallegos:** creo que sí lo tenemos tal cual. Perdón,

**Juan Daniel Vasconez:** así.

**Francisco Gallegos:** así se va a ver ya. Eh, ahora donde creo que pega un poco el impacto es que cuando tú ves un mapa entero y puedes navegar durante todo, te da la impresión de que oye, si es que esto es global, voy a ver más bolas. Es un tradeof gigante,

**Juan Daniel Vasconez:** Aha.

**Francisco Gallegos:** JD. Ah, maldición. Ya, déjale ese. Empecemos así importa. Ah, por si acaso pone el gris. La última. Sí, man. El gris es ahí fue. Y que queda en esa esquina.

**Juan Daniel Vasconez:** Mhm.

**Francisco Gallegos:** Ah, intenta por si acaso googlearte si es que hay como sacar las los valores por ahí que estén volando en las bolas y Yeah.

### **00:29:57** {#00:29:57}

**Juan Daniel Vasconez:** Yeah.

**Francisco Gallegos:** Otra cosa, verad es la vista por default intenta que se vea un gráfico medio lleno. Ya. ¿Cómo hacemos eso artificialmente? Es subiéndole ese parámetro del del tamaño de las bolas. Ya. E ah,

**Juan Daniel Vasconez:** Ya,

**Francisco Gallegos:** así se ve, así se ve de inicio.

**Juan Daniel Vasconez:** eso,

**Francisco Gallegos:** Ver.

**Juan Daniel Vasconez:** eso voy a ver. Creo que así se ve de inicio. Ahí se ve de

**Francisco Gallegos:** Ahí se ve un poco chiquito. Creo que quizá en los controls fijar el

**Juan Daniel Vasconez:** inicio.

**Francisco Gallegos:** zoom en algún mínimo properties position.

**Juan Daniel Vasconez:** No es que eso es para ponerlo más arriba.

**Francisco Gallegos:** Sí, sí, ese no es. Ah. Ah, mira, en eso de los paddings tendrás que jugar un poco con todos los gráficos. Eh, ya creo que es en el visual. Entonces, JD. Map settings, controls, zoom buttons. Pleons, es important, están gigantes. Ya coding, no, más bien. Ah, bueno, sí, en inglés mejor. Sí, sí, sí.

### **00:31:34**

**Francisco Gallegos:** Autoom. A ver, dale un refresh ahí sin el autozom. Creo que queda donde le dejas.

**Juan Daniel Vasconez:** Sí.

**Francisco Gallegos:** Sí, ¿no? Ya, Peppaón.

**Juan Daniel Vasconez:** Mhm.

**Francisco Gallegos:** Ahí está. Y con ese más y menos creo que sí se ve bacán. Ese lazo no creo que hace falta. Ya. Sí, sí, sí.

**Juan Daniel Vasconez:** ¿Dónde?

**Francisco Gallegos:** Preferible que se vea un mapa 100% interactivo antes que un shfil. Ya, bacán. Dale. Si quieres vamos a la otra, una de este.

**Juan Daniel Vasconez:** Estoy

**Francisco Gallegos:** Ya. Igual lo de los filtros ya cachaste,

**Juan Daniel Vasconez:** acá.

**Francisco Gallegos:** ¿no es cierto? lo mismo. Ya. Eh, aquí solo son tres o te falta uno.

**Juan Daniel Vasconez:** Aquí solo son

**Francisco Gallegos:** Ya.

**Juan Daniel Vasconez:** tres.

**Francisco Gallegos:** Entonces, barras, o sea, messages time series y

**Juan Daniel Vasconez:** Ah, no, perdón, aquí. Ah, perdón,

**Francisco Gallegos:** categoría

**Juan Daniel Vasconez:** pensé que te referías a los a los filtros.

### **00:32:47** {#00:32:47}

**Juan Daniel Vasconez:** Son tres filtros, pero sí me falta un un un aquí un plot.

**Francisco Gallegos:** de qué,

**Juan Daniel Vasconez:** Ajá.

**Francisco Gallegos:** ¿cuál es?

**Juan Daniel Vasconez:** Ese es el Djame ver.

**Francisco Gallegos:** ¿Y

**Juan Daniel Vasconez:** Eh, las instituciones y procedimientos que más se pide.

**Francisco Gallegos:** cómo es

**Juan Daniel Vasconez:** Este es un slicer y una barchart.

**Francisco Gallegos:** barras? A ver, regresale está el dashboard. Pues tenemos barras, tenemos Y, ¿cuántas categorías son? Ahí son un huevo,

**Juan Daniel Vasconez:** Ah, sí. Sí,

**Francisco Gallegos:** creo.

**Juan Daniel Vasconez:** son

**Francisco Gallegos:** No, ya.

**Juan Daniel Vasconez:** bastantes.

**Francisco Gallegos:** Eh, okay. Y esa tabla es muy larga. Categoric por

**Juan Daniel Vasconez:** un poco

**Francisco Gallegos:** city.

**Juan Daniel Vasconez:** SCS

**Francisco Gallegos:** Ya. A ver, el gráfico que falta, ¿qué dice?

**Juan Daniel Vasconez:** Eh, o sea, lo que nos dice la es este gráfico de acá, ¿verad? Es estos,

**Francisco Gallegos:** Dos. Son

**Juan Daniel Vasconez:** o sea, van a decirnos,

### **00:34:22**

**Francisco Gallegos:** dos.

**Juan Daniel Vasconez:** va a estar unido en uno solo con va a ser con un filtro. Ajá. Pero solo parece gráfico.

**Francisco Gallegos:** Ese gráfico está medio medio raro. Va a ser medio confuso. Como que un filtro para un gráfico. Si tenemos los filtros para todos.

**Juan Daniel Vasconez:** Mhm.

**Francisco Gallegos:** Ya puedes regresarle, amigo, please. Y ya verás ese Messengers Time series, ¿qué más? ¿Qué colores no más tiene? ¿Qué significa?

**Juan Daniel Vasconez:** Eh, este los colores van a ser de cada una de las eh de las categorías. Ajá. Pero justo ahorita estaba cambiándole la paleta para que se coordine con estos. Pero ahorita le voy a poner las leyendas también. Ahí está.

**Francisco Gallegos:** Y son esas 2 4 6 ocho. Ocho categorías.

**Juan Daniel Vasconez:** Sí.

**Francisco Gallegos:** Ya está mucho para un gráfico de series de tiempo, ocho categorías. Y otra cosa es e este message time series, ¿no tenemos algo parecido en la anterior vista?

**Juan Daniel Vasconez:** Eh, este, tenemos eh los usuarios activos.

**Francisco Gallegos:** Ah, ya.

### **00:35:56**

**Francisco Gallegos:** Sacán, bro. Solo. Esto, pásale la pásale una línea roja en otro eje que sean los mensajes y este gráfico sale de acá.

**Juan Daniel Vasconez:** Ya.

**Francisco Gallegos:** Simón.

**Juan Daniel Vasconez:** ¿Dónde le pasó?

**Francisco Gallegos:** Ah, a ver, ¿de dónde sacas de la el el cómputo de los de los mensajes a través del tiempo?

**Juan Daniel Vasconez:** de contar los mensajes y luego agruparles por categoría.

**Francisco Gallegos:** Ya. Ahorita no necesitamos la agrupación por categoría. O o bueno, sí, pero bueno, intenta, verás, únate al gráfico de la primera pestaña. Ya. Entonces, en ese ponte eh dale un click en active users. Ya.

**Juan Daniel Vasconez:** Mm.

**Francisco Gallegos:** Ahí en X axis, perdón, en secondary Y axis.

**Juan Daniel Vasconez:** Okay,

**Francisco Gallegos:** Ahí, ahí va. Ponle,

**Juan Daniel Vasconez:** ya.

**Francisco Gallegos:** lánzale la suma de mensajes.

**Juan Daniel Vasconez:** Mm.

**Francisco Gallegos:** Messengers.

**Juan Daniel Vasconez:** Pritar.

**Francisco Gallegos:** Ya. Ah, qué lindo gráfico. Ponle en rojo la línea,

**Juan Daniel Vasconez:** ¿Cuál?

### **00:37:30** {#00:37:30}

**Francisco Gallegos:** el azul. Pues

**Juan Daniel Vasconez:** Déjame copiar el hex nada más.

**Francisco Gallegos:** ya. Y deberíamos todo, todo puede filtrarse con la categoría, ¿no es cierto? ¿O no?

**Juan Daniel Vasconez:** Eh, sí. Ajá.

**Francisco Gallegos:** Métele como filtro. Ya, ya está ahí.

**Juan Daniel Vasconez:** Hm.

**Francisco Gallegos:** Perfecto. Listo. Ahora, como si es que nosotros filtramos, ponemos un filtro aquí y ponemos la categoría, nos cambia, ¿no es cierto?

**Juan Daniel Vasconez:** A ver, veamos.

**Francisco Gallegos:** Cópia más bien, no le hagas así. Cópiale lo el que ya tienes arriba y solo cámbiale el

**Juan Daniel Vasconez:** Ok.

**Francisco Gallegos:** Ajá. Ah, ya. Mira, los que veo que no están cambiando son los de arriba.

**Juan Daniel Vasconez:** Los capís.

**Francisco Gallegos:** Ajá.

**Juan Daniel Vasconez:** Ah, es que esos la guía me decía que les desconecte del de estos filtros.

**Francisco Gallegos:** Ya. Sí,

**Juan Daniel Vasconez:** Les conectó.

**Francisco Gallegos:** debería estar conectado. Sí. conecta y desconectar

**Juan Daniel Vasconez:** Sí.

**Francisco Gallegos:** seman.

### **00:39:06**

**Juan Daniel Vasconez:** A ver, creo que es así.

**Francisco Gallegos:** Ah, sí, claro. Por ejemplo, si es que yo selecciono la bola de Colombia,

**Juan Daniel Vasconez:** No,

**Francisco Gallegos:** perdón, de esa Medellín. Dale, pum. Todo cambió, ¿no?

**Juan Daniel Vasconez:** sí.

**Francisco Gallegos:** Lindo. Ya, esa es la nota. Ese es el poder de esta huevada que tenemos que explotar, ¿eh? Entonces, verás, ya ahora que ya está, que ya nosotros tenemos, mira, el análisis que antes tú mostrabas a través de un gráfico con todas las líneas,

**Juan Daniel Vasconez:** Mhm.

**Francisco Gallegos:** ahora está embebido en un filtro y un gráfico. Ya. Entonces, eh, ¿por qué eso quedó eh cuál era la intención de hacer eso? JD volarte, darte espacio en el siguiente dash.

**Juan Daniel Vasconez:** Ya,

**Francisco Gallegos:** Verás,

**Juan Daniel Vasconez:** esta se va de acá.

**Francisco Gallegos:** se va. Ya no tiene sentido. Ya verás. Entonces, hazle grande esa tabla. Ya te entró. Perfecto, son todas, ¿no? Y ahora, ¿por qué ciudad y categoría?

### **00:40:30** {#00:40:30}

**Juan Daniel Vasconez:** Porque ahí pueden saber en qué ciudad se pide más ayuda humanitaria, más empleo, más organizaciones, servicios.

**Francisco Gallegos:** Ya, verás, un filtro, perdón, un formato instantáneo en este tipo de de tablas es utilizar los colores.

**Juan Daniel Vasconez:** Mhm.

**Francisco Gallegos:** e en visual el mismo. Y por ejemplo, ajá, mira, tú puedes fijar ahí los vales dependiendo de tanto tanto. Si es un poco, tienes que que monearle ya. Entonces, tú puedes hacer algunas cosas o los o los colores del del

**Juan Daniel Vasconez:** Okay.

**Francisco Gallegos:** de los números cambian dependiendo siento rango o el fondo de la celda, ¿ya? Para que se nos pinten ciertas celdas. Ahora, si es que hacemos lo segundo, ya no tiene sentido que nosotros tengamos esta sombrita gris pasando una fila. Ya. Entonces, le quitaríamos ese formato de gris a la tabla. E debemos, por ejemplo, diferenciar lo que es ciudad y lo que son los encabezados de la tabla. Les puedes poner en negros,

**Juan Daniel Vasconez:** Mhm.

**Francisco Gallegos:** ¿ya? O en o en un en un font más grande, ¿ya? M. Ahora, e lo que nos queda pendiente era otra otra otro. Ahí nos puede entrar, mira, igualito.

### **00:42:10** {#00:42:10}

**Francisco Gallegos:** Si es que tú le copias a ese de arriba y le duplicas en ese espacio, solo cambiamos la categoría. Solo ajá, solo cambiamos una variable.

**Juan Daniel Vasconez:** Me perdí. No sé qué me dijiste.

**Francisco Gallegos:** Verás este message by category. Ya nos tenemos espacio para un análisis adicional

**Juan Daniel Vasconez:** Hm.

**Francisco Gallegos:** ahorita.

**Juan Daniel Vasconez:** Ajá.

**Francisco Gallegos:** Ya.

**Juan Daniel Vasconez:** Sí.

**Francisco Gallegos:** ¿Cuál era el que nos faltaba?

**Juan Daniel Vasconez:** Eh, esto es de acá.

**Francisco Gallegos:** Ya. Um, y este de los procedimientos no se ve en la tabla.

**Juan Daniel Vasconez:** Sí, pero solo nos dice que buscan información sobre esto, pero no nos dice qué procedimientos O aquí podría ir una Word Cloud por categoría,

**Francisco Gallegos:** No,

**Juan Daniel Vasconez:** ¿no?

**Francisco Gallegos:** no es World. Dejémosle para todo lo que es texto al último. Mm.

**Juan Daniel Vasconez:** Ok.

**Francisco Gallegos:** Es que sabes que creo la tabla necesita más espacio. Es que sabes que yo no sé si ahorita sí, JD.

**Juan Daniel Vasconez:** Mhm.

**Francisco Gallegos:** E le vamos a quitar la ciudad de la tabla y le vamos a hacer como si fuera un filtro,

### **00:44:11**

**Juan Daniel Vasconez:** Ya.

**Francisco Gallegos:** ¿eh? Ah, ya tienes ahí. Sí, sí. No, ya.

**Juan Daniel Vasconez:** Sí.

**Francisco Gallegos:** Entonces, ¿para qué? Para centrarnos en tres análisis que se conecten con los mismos filtros toditos. Ya tenemos procedimientos, categorías y cuál es el otro,

**Juan Daniel Vasconez:** Instituciones.

**Francisco Gallegos:** instituciones. Genial. Ya, tres gráficos en este, eh, y ya no lo haces el cruce con la con la ciudad, sino ahí te queda más simple.

**Juan Daniel Vasconez:** Yeah.

**Francisco Gallegos:** Yeah. Eh, claro, los KPI igual conectados a la nota. Ya. Ahora, ¿cómo te puede quedar bien distribuido esto? E, ¿qué es lo que qué es lo más grande? ¿Qué es lo que generaliza todo?

**Juan Daniel Vasconez:** Ah, ¿qué te refieres?

**Francisco Gallegos:** O sea, ¿qué es lo más qué contiene a qué? El trámite contiene a la institución o la institución al trámite

**Juan Daniel Vasconez:** la institución al trámite y la categoría a las instituciones y

**Francisco Gallegos:** o

**Juan Daniel Vasconez:** trámites.

**Francisco Gallegos:** ya. ¿Cuántas? Esas son todas las categorías, ¿no es cierto?

### **00:45:51**

**Juan Daniel Vasconez:** Sí.

**Francisco Gallegos:** Ya. Y instituciones, ¿cuántas tiene?

**Juan Daniel Vasconez:** Hm. Es que esta depende de cada de cada uno. Ajá.

**Francisco Gallegos:** O que

**Juan Daniel Vasconez:** Es que esta depende de la categoría porque esto analiza los mensajes y va contando las veces que se mencionan estas palabras.

**Francisco Gallegos:** o sea, debería estar primero la institución.

**Juan Daniel Vasconez:** Creo que no estamos confundiendo la pregunta,

**Francisco Gallegos:** A ver.

**Juan Daniel Vasconez:** o sea, a lo que me refiero es que esta tiene todas las categorías y suponiendo que pongamos

**Francisco Gallegos:** Dale.

**Juan Daniel Vasconez:** un un filtro de categoría, ¿no? Este este no va a tener los mismos aquí ni el mismo orden.

**Francisco Gallegos:** Es que mensajes por categoría. por categoría, ya no hace falta tener categoría,

**Juan Daniel Vasconez:** Claro, se podría ir como un

**Francisco Gallegos:** ¿no? O sea,

**Juan Daniel Vasconez:** número.

**Francisco Gallegos:** me refiero como filtro porque si tú le das un click ya te filtra todo y nos interesa saber el análisis por todo eso.

**Juan Daniel Vasconez:** Ajá.

**Francisco Gallegos:** Ya. Entonces, ponte, yo le quitaría category como filtro.

### **00:47:24**

**Francisco Gallegos:** Ya. E entonces, lo primero que podemos mostrar en esta vista es Ajá.

**Juan Daniel Vasconez:** Yeah.

**Francisco Gallegos:** El conteo de mensajes por categoría. Bien, ya que tenemos eso. Luego e lo mismo por institución, lo mismo por eh estos tópicos.

**Juan Daniel Vasconez:** Claro, serían las tres barras.

**Francisco Gallegos:** Esa es La nota ahorita. ¡Puta madre\! Las barras se ve feísimo. 3 estoy viendo qué más podríamos poner.

**Juan Daniel Vasconez:** A menos de que no pongamos esto y pongamos otro plata.

**Francisco Gallegos:** ¿Con cuál?

**Juan Daniel Vasconez:** H este tal vez es

**Francisco Gallegos:** Es que igual es y ese cómo es que se

**Juan Daniel Vasconez:** bar.

**Francisco Gallegos:** hace.

**Juan Daniel Vasconez:** Este es contando la cantidad de de interacciones que tuvieron con el bot.

**Francisco Gallegos:** Sí, sí, está bueno eso, pero a ver, es que sí sabes, JD, yo creo que lo que estamos pensando es que nosotros en lugar de hacer tres gráficos de barras se puede llegar a lo mismo si es que tú filtras lo suficiente, ¿no es cierto?

**Juan Daniel Vasconez:** Sí,

**Francisco Gallegos:** Podemos poner uno de barras con bastante

**Juan Daniel Vasconez:** o sea, podríamos poner un filtro de dos opciones que sea

### **00:49:05**

**Francisco Gallegos:** filtro.

**Juan Daniel Vasconez:** e instituciones o categoría o instituciones o procedimientos,

**Francisco Gallegos:** No, pues son dos análisis diferentes,

**Juan Daniel Vasconez:** pero funcionan igual en cómo se procesa.

**Francisco Gallegos:** pero suponte en este está bien que les tengas un rojo y un verde. Ponte. Mm. Ya. A ver, entonces son dos iguales, uno rojo, uno verde. Tan, tan, tan. Y luego puedes tener, ¿cuál era el que te quedaba? Jd me puedes regresarle, por favor. Más abajo tenías

**Juan Daniel Vasconez:** Ah, Este,

**Francisco Gallegos:** otro.

**Juan Daniel Vasconez:** ese, ese ya está en la primera. Está en la primera. Este, el de qué tanto interactúan.

**Francisco Gallegos:** Y ya. Y estos esas categorías de Rise y esas fueron hechas por nosotros ya.

**Juan Daniel Vasconez:** Sí,

**Francisco Gallegos:** Y todo lo de satisfaction.

**Juan Daniel Vasconez:** aquí esto puede ser una una donut. Esto puede ser un filtro y esto puede ser una

**Francisco Gallegos:** No, eso eso para mí

**Juan Daniel Vasconez:** donut.

**Francisco Gallegos:** es eso para mí es una dona compuesta. Puede ser potentazo, pero estas dos sí necesitamos.

### **00:50:48**

**Juan Daniel Vasconez:** Mhm.

**Francisco Gallegos:** Pero escacha este y el de arriba son dos recontra que útiles. Entonces verás.

**Juan Daniel Vasconez:** M.

**Francisco Gallegos:** Ah, verás.O Todavía hagamos lo siguiente. Ah, ándate al al Power BI. Ya verás, hazle,

**Juan Daniel Vasconez:** Yep.

**Francisco Gallegos:** vamos a ordenarles así, cuatro plots, ya la barra de color de verdes con degradados, tal como le tienes en el notebook para categorías. No, no, ese no. Derriba primero.

**Juan Daniel Vasconez:** o el este de acá.

**Francisco Gallegos:** Es ya vamos a hacer exactamente estos dos análisis que tienes igualito, uno arriba, uno abajo, en rojos y en verdes. Ya. Ajá.

**Juan Daniel Vasconez:** Ya,

**Francisco Gallegos:** Hasta en sólidos creo que se ve bien. No pasa nada. Ya. Entonces, esos dos por el lado de la izquierda y en el lado

**Juan Daniel Vasconez:** ya.

**Francisco Gallegos:** que nos queda tenemos para espacio para dos más cachas.

**Juan Daniel Vasconez:** Mm.

**Francisco Gallegos:** Vamos a meter estos dos análisis en una dona, ya vamos a incorporar el usefulness rating e y ver si es que le podemos cruzar con el W

**Juan Daniel Vasconez:** Mm.

**Francisco Gallegos:** recommend, con una clave de color.

### **00:52:12**

**Juan Daniel Vasconez:** Ya.

**Francisco Gallegos:** Puede ser. Ya. Ajá. Eh, me parece que sí hay como meter un anillo de dos niveles en esto.

**Juan Daniel Vasconez:** Okay.

**Francisco Gallegos:** Ah, chécale ya. Eh, pero es que esto es recontraútil porque te dice me sirve o no. Y eso es full importante. Ya. Y luego el de abajo es para medir el engagement, perdón,

**Juan Daniel Vasconez:** Mhm.

**Francisco Gallegos:** el que estaba más arriba. Ya. Este le puedes hacer barras este verticales, ¿ya?

**Juan Daniel Vasconez:** Mhm.

**Francisco Gallegos:** E o aquí también creo que nos funcionaría este gráfico del trimap. Porque son pocas categorías.

**Juan Daniel Vasconez:** Ya.

**Francisco Gallegos:** Más abajo está ese de cuadraditos chiquito. Ahí ya.

**Juan Daniel Vasconez:** Este

**Francisco Gallegos:** Oh, pruébale, pruébale cuál se ve bien para variar un poco. Ya.

**Juan Daniel Vasconez:** ya.

**Francisco Gallegos:** Entonces ahí sí estamos contando en esta misma pestaña qué te están pidiendo y qué tan bueno es tu servicio. Puede ser. Ya, incluso, JD, el orden creo que puede ir en la dona

**Juan Daniel Vasconez:** Okay.

### **00:53:30** {#00:53:30}

**Francisco Gallegos:** primero a la derecha la el gráfico este del engagement, ¿ya? Y abajo las barras en verde y y al otro lado las barras en rojo. Sí. Eh, pruébale así o pruébale como le vimos antes de ver cuál funciona mejor. Eh, porque visualmente ya te de entrada te cachas que te está que te está contando el dashboard. Ya.

**Juan Daniel Vasconez:** Ya.

**Francisco Gallegos:** Eh, y ahora verás, algo que está muy útil es pensar en, por ejemplo, eh hacer explotar al al máximo los filtros. Ya, como te decía, si es que nosotros ponemos tres filtros en un gráfico,

**Juan Daniel Vasconez:** Mhm.

**Francisco Gallegos:** podemos llegar a tres niveles de tres niveles de análisis diferentes, ¿ya? Entonces,

**Juan Daniel Vasconez:** Mhm.

**Francisco Gallegos:** e fíjate en cuál siempre nos puede ser útil, por ejemplo, el gráfico de ciudad, eh, perdón, el filtro de ciudad en en ambos dashboards funcionan de una. E el gráfico de categoría también,

**Juan Daniel Vasconez:** Mhm.

**Francisco Gallegos:** ¿ya? Entonces, eso mírale cuáles siempre e hace sentido tener eh incluso para llegar a cierto tipo de insight o de análisis, ¿ya? Entonces, e yo creo que con eso estás eso también bores. Em,

### **00:54:50**

**Juan Daniel Vasconez:** Yeah.

**Francisco Gallegos:** y creo que podemos dejarla hasta aquí e hasta saltar al al siguiente. Ya te parece si es que en el siguiente checkpoint vemos e el feedback implementado en la pestaña uno, Samsile y en la otra que es demand experience.

**Juan Daniel Vasconez:** Sí,

**Francisco Gallegos:** suena y con eso ya nos lanzamos a la a la

**Juan Daniel Vasconez:** ya me dale.

**Francisco Gallegos:** tres.

**Juan Daniel Vasconez:** Ya.

**Francisco Gallegos:** Ya. Bacán. Entonces,

**Juan Daniel Vasconez:** Ok.

**Francisco Gallegos:** eh es buen momento para que les vayas formateando a todos de la misma forma esto que te decía, las cajitas, los en la sombra, la separación de los márgenes, el color de los títulos, etcétera. Eh, luego ya es copy paste, copy paste y solo cambia el tipo de gráfico.

**Juan Daniel Vasconez:** Ya amigo de

**Francisco Gallegos:** Ya, ya, JD está una bestia buen trabajo. Ya, bacán.

**Juan Daniel Vasconez:** una eh

**Francisco Gallegos:** ¿Qué tal te parece hasta ahora el Power B?

**Juan Daniel Vasconez:** útil pero retrógrado porque todo esto con

**Francisco Gallegos:** Poco no. Sí,

**Juan Daniel Vasconez:** Python la mitad del tiempo.

**Francisco Gallegos:** claro. Pero imagínate empresas que tienen todo en Excel.

**Juan Daniel Vasconez:** Claro.

**Francisco Gallegos:** Sí, ahí es donde ahí está su core,

**Juan Daniel Vasconez:** Ajá.

**Francisco Gallegos:** su nicho y ya.

**Juan Daniel Vasconez:** Sí, sí, sí.

**Francisco Gallegos:** Bueno, JD, entonces me avisas, no sé, mañana tardecito igual a la misma hora o antes, no sé.

**Juan Daniel Vasconez:** Ya te voy avisando según cómo vaya con este.

**Francisco Gallegos:** Bro, nos vemos.

**Juan Daniel Vasconez:** amigo de unaito.

**Francisco Gallegos:** Chao. Bye.

**Juan Daniel Vasconez:** Una buena tarde.

### **La transcripción finalizó después de 00:56:35**

*Esta transcripción editable se generó por computadora y puede contener errores. Los usuarios también pueden cambiar el texto después de que se cree.*