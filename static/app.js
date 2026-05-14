(function () {
    const toast = document.getElementById('toast');
    let toastTimer = null;

    async function json(url, options = {}) {
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...(options.headers || {}),
            },
            ...options,
        });

        let payload = null;
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            payload = await response.json();
        } else {
            const text = await response.text();
            payload = { error: text || `Request failed with status ${response.status}` };
        }

        if (!response.ok) {
            const error = new Error(payload.error || `Request failed with status ${response.status}`);
            error.status = response.status;
            error.data = payload;
            throw error;
        }

        return payload;
    }

    function number(value) {
        const numeric = Number(value || 0);
        if (Number.isInteger(numeric)) {
            return numeric.toString();
        }
        return numeric.toFixed(1).replace(/\.0$/, '');
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#39;');
    }

    function showToast(message, tone = 'success') {
        if (!toast) return;
        toast.textContent = message;
        toast.dataset.tone = tone;
        toast.classList.add('show');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => {
            toast.classList.remove('show');
        }, 2600);
    }

    window.mt = {
        json,
        number,
        escapeHtml,
        showToast,
    };
})();
