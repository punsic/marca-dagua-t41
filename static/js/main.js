document.addEventListener('DOMContentLoaded', () => {
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('pdfFileInput');
    const uploadContent = dropzone.querySelector('.upload-content');
    const fileInfo = document.getElementById('fileInfo');
    const selectedFileName = document.getElementById('selectedFileName');
    const btnRemoveFile = document.getElementById('btnRemoveFile');
    const form = document.getElementById('watermarkForm');
    const btnSubmit = document.getElementById('btnSubmit');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const localIpAddress = document.getElementById('localIpAddress');

    // Atualiza o rodapé com o link de acesso atual
    if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
        localIpAddress.innerText = window.location.origin;
    } else {
        localIpAddress.innerText = `http://[IP_DO_COMPUTADOR]:${window.location.port || '5000'}`;
    }

    // Drag and drop events
    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
        }, false);
    });

    dropzone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleFileSelect(files[0]);
        }
    });

    // Click on dropzone to select file
    dropzone.addEventListener('click', (e) => {
        // Prevent trigger if clicking on remove button
        if (e.target !== btnRemoveFile) {
            fileInput.click();
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            handleFileSelect(fileInput.files[0]);
        }
    });

    // Remove selected file
    btnRemoveFile.addEventListener('click', (e) => {
        e.stopPropagation(); // Impede abrir seletor
        resetFileSelection();
    });

    function handleFileSelect(file) {
        if (file.type !== 'application/pdf' && !file.name.toLowerCase().endswith('.pdf')) {
            alert('Por favor, selecione apenas arquivos PDF.');
            resetFileSelection();
            return;
        }

        selectedFileName.innerText = file.name;
        uploadContent.style.display = 'none';
        fileInfo.style.display = 'flex';
        dropzone.style.borderColor = 'var(--secondary)';
        
        // Atribui o arquivo ao input (necessário se veio do drop)
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(file);
        fileInput.files = dataTransfer.files;
    }

    function resetFileSelection() {
        fileInput.value = '';
        uploadContent.style.display = 'flex';
        fileInfo.style.display = 'none';
        dropzone.style.borderColor = 'var(--border)';
    }

    // Submit form and request PDF protect
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        if (fileInput.files.length === 0) {
            alert('Selecione um arquivo PDF primeiro.');
            return;
        }

        const formData = new FormData(form);
        
        // Mostra animação de carregamento
        loadingOverlay.style.display = 'flex';
        btnSubmit.disabled = true;

        try {
            const response = await fetch('/api/watermark', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Erro desconhecido ao processar arquivo.');
            }

            // Lê o arquivo retornado como Blob
            const blob = await response.blob();
            
            // Extrai o nome do arquivo das headers de Content-Disposition se disponível
            let filename = 'documento_protegido.pdf';
            const disposition = response.headers.get('content-disposition');
            if (disposition && disposition.indexOf('attachment') !== -1) {
                const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
                const matches = filenameRegex.exec(disposition);
                if (matches != null && matches[1]) { 
                    filename = matches[1].replace(/['"]/g, '');
                    // Corrige possíveis encodings
                    filename = decodeURIComponent(escape(filename));
                }
            }

            // Cria link temporário para download automático
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(downloadUrl);

            // Reseta formulário após sucesso
            resetFileSelection();
            form.reset();

        } catch (error) {
            alert(`Erro: ${error.message}`);
        } finally {
            loadingOverlay.style.display = 'none';
            btnSubmit.disabled = false;
        }
    });
});
