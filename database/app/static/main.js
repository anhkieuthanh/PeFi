document.addEventListener('DOMContentLoaded', ()=>{
  const tabs = document.querySelectorAll('.tab');
  const panels = document.querySelectorAll('.panel');
    // Chart.js global polish for a modern, refined look
    if (window.Chart) {
      Chart.defaults.font.family = 'Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial';
      Chart.defaults.color = '#6b7280';
      Chart.defaults.scale.grid.color = 'rgba(17,24,39,0.06)';
      Chart.defaults.plugins.legend.labels.boxWidth = 12;
      Chart.defaults.plugins.legend.labels.boxHeight = 12;
      Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(255,255,255,0.95)';
      Chart.defaults.plugins.tooltip.borderColor = 'rgba(17,24,39,0.08)';
      Chart.defaults.plugins.tooltip.borderWidth = 1;
      Chart.defaults.plugins.tooltip.titleColor = '#111827';
      Chart.defaults.plugins.tooltip.bodyColor = '#111827';
    }
  tabs.forEach(t=>t.addEventListener('click', ()=>{
    tabs.forEach(x=>x.classList.remove('active'));
    t.classList.add('active');
    panels.forEach(p=>p.classList.add('hidden'));
    document.getElementById(t.dataset.tab).classList.remove('hidden');
  }));

  // small helpers for chart styling
  const hexToRgb = (hex)=>{
    const c = hex.replace('#','');
    const bigint = parseInt(c,16);
    if(c.length===6){
      return {r:(bigint>>16)&255, g:(bigint>>8)&255, b:bigint&255};
    }
    return {r:77,g:163,b:255};
  };
  const makeGradient = (ctx, hex)=>{
    const {r,g,b} = hexToRgb(hex);
    const grad = ctx.createLinearGradient(0,0,0,200);
    grad.addColorStop(0, `rgba(${r},${g},${b},0.25)`);
    grad.addColorStop(1, `rgba(${r},${g},${b},0.02)`);
    return grad;
  };

  let currentPage = 1;
  let totalPages = 1;
  const PAGE_SIZE = 10;

  function getFilters(){
    const start = document.getElementById('start').value;
    const end = document.getElementById('end').value;
    const type = document.getElementById('type').value;
    const cats = Array.from(document.getElementById('categories').selectedOptions).map(o=>o.value);
    const params = new URLSearchParams();
    if(start) params.set('start', start);
    if(end) params.set('end', end);
    if(type && type !== 'all') params.set('type', type);
    if(cats.length) params.set('categories', cats.join(','));
    params.set('page', String(currentPage));
    params.set('page_size', String(PAGE_SIZE));
    return params;
  }

  function renderPager(pagination){
    const info = document.getElementById('pageInfo');
    const btnPrev = document.getElementById('prevPage');
    const btnNext = document.getElementById('nextPage');
    currentPage = pagination?.page || 1;
    totalPages = pagination?.total_pages || 1;
    info.textContent = `Trang ${currentPage}/${totalPages}`;
    btnPrev.disabled = currentPage <= 1;
    btnNext.disabled = currentPage >= totalPages;
  }

  // fetch and render dashboard data
  async function loadData(){
    try{
      const resp = await fetch(`/dashboard_data?${getFilters().toString()}`);
      const data = await resp.json();
      document.getElementById('income').innerText = new Intl.NumberFormat('vi-VN').format(data.monthly.income);
      document.getElementById('expense').innerText = new Intl.NumberFormat('vi-VN').format(data.monthly.expense);

      // timeseries chart with refined palette and smooth fills
  const colors = ['#0a84ff','#ef4444','#f59e0b','#10b981'];
      const tsCtx = document.getElementById('tsChart').getContext('2d');
      new Chart(tsCtx, {
        type:'line',
        data:{labels:data.timeseries.labels, datasets:[
          {label:'Thu',data:data.timeseries.income,borderColor:colors[0],backgroundColor:makeGradient(tsCtx, colors[0]),fill:true,tension:0.35,borderWidth:2.4,pointRadius:0,pointHitRadius:10},
          {label:'Chi',data:data.timeseries.expense,borderColor:colors[1],backgroundColor:makeGradient(tsCtx, colors[1]),fill:true,tension:0.35,borderWidth:2.4,pointRadius:0,pointHitRadius:10}
        ]},
        options:{
          plugins:{legend:{display:true}},
          scales:{y:{beginAtZero:true}}
        }
      });

      // category chart
      const catCtx = document.getElementById('catChart').getContext('2d');
      new Chart(catCtx, {
        type:'doughnut',
        data:{
          labels:data.by_category.map(x=>x.category),
          datasets:[{data:data.by_category.map(x=>x.amount),backgroundColor:colors,borderWidth:0}]
        },
        options:{plugins:{legend:{position:'bottom'}}, cutout:'62%'}
      });

      // populate transactions table
      const tbody = document.querySelector('#txTable tbody');
      tbody.innerHTML = '';
      // SVG icon strings
      const coinSVG = `<svg class="icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="10" fill="var(--accent)"/><circle cx="12" cy="12" r="6" fill="#fff" opacity="0.9"/></svg>`;
      const paySVG = `<svg class="icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="2" y="6" width="20" height="12" rx="2" fill="#000" opacity="0.9"/><rect x="4" y="9" width="16" height="6" fill="#fff" opacity="0.95"/></svg>`;
  (data.transactions || []).forEach(tx=>{
        const tr = document.createElement('tr');
        const iconHTML = tx.type === 'income' ? coinSVG : paySVG;
        tr.innerHTML = `
          <td>${tx.date}</td>
          <td class="merchant-cell">${iconHTML}<span>${tx.merchant}</span></td>
          <td>${tx.category}</td>
          <td class="tx-amount ${tx.type}">${new Intl.NumberFormat('vi-VN').format(tx.amount)}</td>
          <td>${tx.type}</td>
        `;
        tbody.appendChild(tr);
      });

      // populate categories multi-select for report controls
      const catSelect = document.getElementById('r_categories');
      catSelect.innerHTML = '';
      data.by_category.forEach(c=>{
        const opt = document.createElement('option'); opt.value=c.category; opt.innerText=c.category; catSelect.appendChild(opt);
      });

      // also populate top filter categories (keep existing selections when possible)
      const topCat = document.getElementById('categories');
      const selectedVals = new Set(Array.from(topCat.selectedOptions).map(o=>o.value));
      topCat.innerHTML = '';
      data.by_category.forEach(c=>{
        const opt = document.createElement('option'); opt.value=c.category; opt.innerText=c.category; if(selectedVals.has(c.category)) opt.selected = true; topCat.appendChild(opt);
      });

      // render pager
      renderPager(data.pagination);

      // report generation handler
      document.getElementById('generateReport').addEventListener('click', ()=>{
        const rs = document.getElementById('r_start').value;
        const re = document.getElementById('r_end').value;
        const rtype = document.getElementById('r_type').value;
        const selected = Array.from(catSelect.selectedOptions).map(o=>o.value);

        const filtered = (data.transactions || []).filter(tx=>{
          if(rtype !== 'all' && tx.type !== rtype) return false;
          if(selected.length && !selected.includes(tx.category)) return false;
          if(rs && tx.date < rs) return false;
          if(re && tx.date > re) return false;
          return true;
        });

        // summary
        const total = filtered.reduce((s,v)=>s + v.amount*((v.type==='income')?1:-1),0);
        document.getElementById('reportSummary').innerText = `Tổng (thu-chi): ${new Intl.NumberFormat('vi-VN').format(total)}`;
        document.getElementById('reportResult').classList.remove('hidden');

        // report table
        const rtbody = document.querySelector('#reportTable tbody'); rtbody.innerHTML='';
        filtered.forEach(tx=>{
          const tr = document.createElement('tr');
          tr.innerHTML = `<td>${tx.date}</td><td>${tx.merchant}</td><td>${tx.category}</td><td>${new Intl.NumberFormat('vi-VN').format(tx.amount)}</td><td>${tx.type}</td>`;
          rtbody.appendChild(tr);
        });

        // report chart: group by category amounts
        const byCat = {};
        filtered.forEach(tx=>{ byCat[tx.category] = (byCat[tx.category]||0) + tx.amount; });
        const labels = Object.keys(byCat);
        const values = labels.map(l=>byCat[l]);
        const rctx = document.getElementById('reportChart').getContext('2d');
        if(window.reportChart) window.reportChart.destroy();
        window.reportChart = new Chart(rctx, {type:'bar', data:{labels, datasets:[{label:'Total',data:values,backgroundColor:colors,borderRadius:6,maxBarThickness:36}]}, options:{plugins:{legend:{display:false}}}});
      });

    }catch(e){
      console.error('Could not load dashboard data', e);
    }
  }

  loadData();

  document.getElementById('apply').addEventListener('click', ()=>{
    currentPage = 1;
    loadData();
  });

  document.getElementById('prevPage').addEventListener('click', ()=>{
    if(currentPage > 1){ currentPage -= 1; loadData(); }
  });
  document.getElementById('nextPage').addEventListener('click', ()=>{
    if(currentPage < totalPages){ currentPage += 1; loadData(); }
  });
});
