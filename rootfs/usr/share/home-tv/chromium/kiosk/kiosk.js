let hidePointer;

document.addEventListener('contextmenu', event => event.preventDefault(), true);
document.addEventListener('pointermove', event => {
    const root = document.documentElement;
    if (event.pointerType !== 'mouse' || !root) {
        return;
    }
    root.setAttribute('data-hometv-pointer', '');
    clearTimeout(hidePointer);
    hidePointer = setTimeout(() => root.removeAttribute('data-hometv-pointer'), 4000);
}, { passive: true });
