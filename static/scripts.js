document.addEventListener('DOMContentLoaded', function() {
    const socket = io('http://' + document.domain + ':' + location.port + '/dashboard');
    const registrosBody = document.getElementById('registrosBody');
    const searchInput = document.getElementById('searchInput');
    const refreshBtn = document.getElementById('refreshBtn');
    const totalCount = document.getElementById('totalCount');
    const pendingCount = document.getElementById('pendingCount');
    const processedCount = document.getElementById('processedCount');
    
    // Modal para imágenes
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.innerHTML = `
        <span class="modal-close">&times;</span>
        <img class="modal-content" id="modalImage">
    `;
    document.body.appendChild(modal);
    
    // Cargar registros iniciales
    loadRegistros();
    
    // Eventos de SocketIO
    socket.on('connect', () => {
        console.log('Conectado al servidor en tiempo real');
    });
    
    socket.on('nuevo_registro', (registro) => {
        addRegistroToTable(registro);
        updateStats();
    });
    
    socket.on('actualizacion_analisis', (registro) => {
        updateRegistro(registro);
        updateStats();
    });
    
    // Buscar registros
    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase();
        const rows = registrosBody.getElementsByTagName('tr');
        
        for (let row of rows) {
            const ubicacion = row.cells[2].textContent.toLowerCase();
            const tipoSensor = row.cells[1].textContent.toLowerCase();
            
            if (ubicacion.includes(searchTerm) || tipoSensor.includes(searchTerm)) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        }
    });
    
    // Botón de actualizar
    refreshBtn.addEventListener('click', loadRegistros);
    
    // Cerrar modal
    modal.querySelector('.modal-close').addEventListener('click', () => {
        modal.style.display = 'none';
    });
    
    // Cerrar modal al hacer clic fuera
    window.addEventListener('click', (event) => {
        if (event.target === modal) {
            modal.style.display = 'none';
        }
    });
    
    // Función para cargar todos los registros
    function loadRegistros() {
        fetch('/api/sensor/todos')
            .then(response => response.json())
            .then(data => {
                registrosBody.innerHTML = '';
                data.forEach(registro => {
                    addRegistroToTable(registro);
                });
                updateStats();
            })
            .catch(error => console.error('Error al cargar registros:', error));
    }
    
    // Función para agregar un registro a la tabla
    function addRegistroToTable(registro) {
        const row = document.createElement('tr');
        row.dataset.id = registro._id;
        
        const fecha = new Date(registro.fecha).toLocaleString();
        const imagenUrl = `/api/sensor/imagen/${registro.nombre_archivo}`;
        
        row.innerHTML = `
            <td>${fecha}</td>
            <td>${registro.tipo_sensor}</td>
            <td>${registro.ubicacion}</td>
            <td class="analisis-text">
                ${getStatusIcon(registro)} ${registro.analisis || 'En análisis...'}
            </td>
            <td>
                <img src="${imagenUrl}" alt="Miniatura" class="thumbnail" data-src="${imagenUrl}">
            </td>
            <td>
                <button class="btn btn-download" data-url="${imagenUrl}">Descargar</button>
                <button class="btn btn-view" data-src="${imagenUrl}">Ver</button>
            </td>
        `;
        
        registrosBody.insertBefore(row, registrosBody.firstChild);
        
        // Agregar eventos a los botones e imágenes
        row.querySelector('.thumbnail').addEventListener('click', showImageModal);
        row.querySelector('.btn-view').addEventListener('click', showImageModal);
        row.querySelector('.btn-download').addEventListener('click', downloadImage);
    }
    
    // Función para actualizar un registro existente
    function updateRegistro(registro) {
        const row = document.querySelector(`tr[data-id="${registro._id}"]`);
        if (row) {
            const analisisCell = row.cells[3];
            analisisCell.innerHTML = `${getStatusIcon(registro)} ${registro.analisis || 'Error en análisis'}`;
        }
    }
    
    // Función para actualizar las estadísticas
    function updateStats() {
        const rows = registrosBody.getElementsByTagName('tr');
        totalCount.textContent = rows.length;
        
        let pending = 0;
        let processed = 0;
        
        for (let row of rows) {
            const statusIcon = row.cells[3].querySelector('.status-indicator');
            if (statusIcon.classList.contains('status-pending')) {
                pending++;
            } else {
                processed++;
            }
        }
        
        pendingCount.textContent = pending;
        processedCount.textContent = processed;
    }
    
    // Función para obtener el icono de estado
    function getStatusIcon(registro) {
        if (!registro.procesado) {
            return '<span class="status-indicator status-pending" title="Pendiente"></span>';
        } else if (registro.analisis && !registro.analisis.includes('Error')) {
            return '<span class="status-indicator status-processed" title="Procesado"></span>';
        } else {
            return '<span class="status-indicator status-error" title="Error en análisis"></span>';
        }
    }
    
    // Función para mostrar la imagen en modal
    function showImageModal(event) {
        const imageUrl = event.target.dataset.src;
        const modalImg = document.getElementById('modalImage');
        modalImg.src = imageUrl;
        modal.style.display = 'block';
    }
    
    // Función para descargar imagen
    function downloadImage(event) {
        const imageUrl = event.target.dataset.url;
        const link = document.createElement('a');
        link.href = imageUrl;
        link.download = imageUrl.split('/').pop();
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
});
