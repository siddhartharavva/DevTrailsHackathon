// Simple Router
function nav(targetId) {
    document.querySelectorAll('.screen').forEach(el => {
        el.classList.remove('active');
        el.classList.add('slide-out');
    });
    
    setTimeout(() => {
        document.querySelectorAll('.screen').forEach(el => el.classList.remove('slide-out'));
        const target = document.getElementById(targetId);
        if (target) {
            target.classList.add('active');
        }
    }, 150);
}

// Selectable logic
document.querySelectorAll('.btn-outline').forEach(btn => {
    btn.addEventListener('click', (e) => {
        // Find parent grid
        const parent = e.currentTarget.parentElement;
        parent.querySelectorAll('.btn-outline').forEach(b => b.classList.remove('selected'));
        e.currentTarget.classList.add('selected');
    });
});

function selectPlan(el) {
    document.querySelectorAll('.plan-card').forEach(c => {
        c.classList.remove('selected');
        const title = c.querySelector('.plan-title');
        const price = c.querySelector('.plan-price');
        const priceSub = c.querySelector('.plan-price-sub');
        if (title) title.classList.remove('text-white');
        if (price) price.classList.remove('text-blue');
        if (priceSub) priceSub.classList.remove('text-blue');
    });
    
    el.classList.add('selected');
    const title = el.querySelector('.plan-title');
    const price = el.querySelector('.plan-price');
    const priceSub = el.querySelector('.plan-price-sub');
    
    if (title) title.classList.add('text-white');
    if (price) price.classList.add('text-blue');
    if (priceSub) priceSub.classList.add('text-blue');
}
