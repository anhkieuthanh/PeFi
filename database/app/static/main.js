document.addEventListener('DOMContentLoaded', () => {
  const tabs = document.querySelectorAll('.tab');
  const panels = document.querySelectorAll('.panel');
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
  tabs.forEach(t => t.addEventListener('click', () => {
    tabs.forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    panels.forEach(p => p.classList.add('hidden'));
    document.getElementById(t.dataset.tab).classList.remove('hidden');
  }));

  const hexToRgb = (hex) => {
    const c = hex.replace('#', '');
    const bigint = parseInt(c, 16);
    return c.length === 6 ? { r: (bigint >> 16) & 255, g: (bigint >> 8) & 255, b: bigint & 255 } : { r: 77, g: 163, b: 255 };
  };
  const makeGradient = (ctx, hex) => {
    const { r, g, b } = hexToRgb(hex);
    const grad = ctx.createLinearGradient(0, 0, 0, ctx.canvas.clientHeight);
    grad.addColorStop(0, `rgba(${r},${g},${b},0.25)`);
    grad.addColorStop(1, `rgba(${r},${g},${b},0.02)`);
    return grad;
  };

  let currentPage = 1;
  let totalPages = 1;

  // Chart instances
  let tsChartInstance = null;
  let categoryTsChartInstance = null; 

  // Ensure loading overlay exists
  function ensureLoadingOverlay(){
    let el = document.getElementById('loadingOverlay');
    if(!el){
      el = document.createElement('div');
      el.id = 'loadingOverlay';
      el.className = 'loading-overlay hidden';
      el.innerHTML = '<div class="spinner"></div>';
      document.body.appendChild(el);
    }
    return el;
  }

  function getFilters() {
    const activeButton = document.querySelector('.timeframe-btn.active');
    const timeframe = activeButton ? activeButton.dataset.frame : '1M';

    const params = new URLSearchParams();
    params.set('timeframe', timeframe);
    params.set('page', String(currentPage));
    // Giả định user_id là 2. Trong ứng dụng thực tế, giá trị này sẽ được lấy sau khi đăng nhập.
    params.set('user_id', '2'); 
    return params;
  }

  function renderPager(pagination) {
    const info = document.getElementById('pageInfo');
    const btnPrev = document.getElementById('prevPage');
    const btnNext = document.getElementById('nextPage');
    currentPage = pagination?.page || 1;
    totalPages = pagination?.total_pages || 1;
    if(info) info.textContent = `Trang ${currentPage}/${totalPages}`;
    if(btnPrev) btnPrev.disabled = currentPage <= 1;
    if(btnNext) btnNext.disabled = currentPage >= totalPages;
  }

  async function loadData() {
    const loadingOverlay = ensureLoadingOverlay();
    loadingOverlay.classList.remove('hidden');

    try {
      // Endpoint là /dashboard_data, port giữ nguyên 5001 theo file run.py
      const apiUrl = `http://127.0.0.1:5001/dashboard_data?${getFilters().toString()}`;
      const resp = await fetch(apiUrl);
      if (!resp.ok) throw new Error(`Lỗi HTTP: ${resp.status}`);
      const data = await resp.json();

  const incomeEl = document.getElementById('income');
  const expenseEl = document.getElementById('expense');
  if (incomeEl) incomeEl.innerText = new Intl.NumberFormat('vi-VN').format(data.monthly.income);
  if (expenseEl) expenseEl.innerText = new Intl.NumberFormat('vi-VN').format(data.monthly.expense);

      const colors = ['#0a84ff', '#ef4444', '#f59e0b', '#10b981', '#7c3aed', '#f472b6'];

      // Biểu đồ Timeseries chính
      const tsCtx = document.getElementById('tsChart').getContext('2d');
      if (tsChartInstance) tsChartInstance.destroy();
      tsChartInstance = new Chart(tsCtx, {
        type: 'line',
        data: {
          labels: data.timeseries.labels,
          datasets: [
            { label: 'Thu', data: data.timeseries.income, borderColor: colors[0], backgroundColor: makeGradient(tsCtx, colors[0]), fill: true, tension: 0.35, borderWidth: 2.4, pointRadius: 0, pointHitRadius: 10 },
            { label: 'Chi', data: data.timeseries.expense, borderColor: colors[1], backgroundColor: makeGradient(tsCtx, colors[1]), fill: true, tension: 0.35, borderWidth: 2.4, pointRadius: 0, pointHitRadius: 10 }
          ]
        },
        options: { plugins: { legend: { display: true } }, scales: { y: { beginAtZero: true } } }
      });

      // Biểu đồ Timeseries theo Danh mục
    const categoryChartContainer = document.getElementById('categoryTsChartContainer');
    if (categoryChartContainer && data.category_timeseries && data.category_timeseries.datasets && data.category_timeseries.datasets.length > 0) {
    categoryChartContainer.classList.remove('hidden');
    const catCanvas = document.getElementById('categoryTsChart');
    if (catCanvas && catCanvas.getContext) {
      const catTsCtx = catCanvas.getContext('2d');
      if (categoryTsChartInstance) categoryTsChartInstance.destroy();

      const categoryDatasets = data.category_timeseries.datasets.map((ds, index) => ({
        ...ds,
        borderColor: colors[(index + 2) % colors.length],
        originalBorderColor: colors[(index + 2) % colors.length],
        backgroundColor: makeGradient(catTsCtx, colors[(index + 2) % colors.length]),
        fill: true, tension: 0.35, borderWidth: 2, pointRadius: 0, pointHitRadius: 10
      }));

      categoryTsChartInstance = new Chart(catTsCtx, {
        type: 'line',
        data: { labels: data.category_timeseries.labels, datasets: categoryDatasets },
        options: {
          scales: { y: { beginAtZero: true } },
          plugins: { legend: { position: 'bottom' } },
          interaction: { mode: 'nearest', intersect: false },
          onHover: (event, activeElements, chart) => {
            // Find the nearest element to reflect actual hovered dataset
            const nearest = chart.getElementsAtEventForMode(event, 'nearest', { intersect: false }, true);
            const hoveredDatasetIndex = nearest && nearest.length ? nearest[0].datasetIndex : undefined;
            if (hoveredDatasetIndex !== undefined) {
              chart.data.datasets.forEach((dataset, i) => {
                dataset.borderColor = i === hoveredDatasetIndex ? dataset.originalBorderColor : 'rgba(107, 114, 128, 0.2)';
              });
            } else {
              chart.data.datasets.forEach(dataset => {
                dataset.borderColor = dataset.originalBorderColor;
              });
            }
            chart.update('none');
          },
          onLeave: (event, chart) => {
            // Restore all series when pointer leaves the chart area
            chart.data.datasets.forEach(dataset => {
              dataset.borderColor = dataset.originalBorderColor;
            });
            chart.update('none');
          }
        }
      });

      // Fallback: reset colors when mouse leaves the canvas
      // Using property assignment avoids accumulating multiple listeners across re-renders
      catCanvas.onmouseleave = () => {
        if (categoryTsChartInstance) {
          categoryTsChartInstance.data.datasets.forEach(ds => {
            ds.borderColor = ds.originalBorderColor;
          });
          categoryTsChartInstance.update('none');
        }
      };
    }
      } else {
    if (categoryChartContainer) categoryChartContainer.classList.add('hidden');
      }

      // Populate bảng giao dịch
      const tbody = document.querySelector('#txTable tbody');
      tbody.innerHTML = '';
      (data.transactions || []).forEach(tx => {
        // Normalize type coming from backend: could be 'income'/'expense', 1/0, or boolean
        const isIncome = tx.type === 'income' || tx.type === 1 || tx.type === '1' || tx.type === true;
        const typeStr = isIncome ? 'income' : 'expense';
        const tr = document.createElement('tr');
        const iconId = isIncome ? 'icon-coin' : 'icon-pay';
        const iconHTML = `<svg class="icon"><use xlink:href="#${iconId}"></use></svg>`;
        tr.innerHTML = `
          <td>${tx.date}</td>
          <td class="merchant-cell">${iconHTML}<span>${tx.merchant}</span></td>
          <td>${tx.category}</td>
          <td class="tx-amount ${typeStr}">${new Intl.NumberFormat('vi-VN').format(tx.amount)}</td>
          <td>${typeStr}</td>
        `;
        tbody.appendChild(tr);
      });

      renderPager(data.pagination);

    } catch (e) {
      console.error('Không thể tải dữ liệu dashboard:', e);
    } finally {
      loadingOverlay.classList.add('hidden');
    }
  }

  // --- EVENT LISTENERS ---
  document.querySelectorAll('.timeframe-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const active = document.querySelector('.timeframe-btn.active');
      if (active) active.classList.remove('active');
      btn.classList.add('active');
      currentPage = 1;
      loadData();
    });
  });

  const prevBtn = document.getElementById('prevPage');
  if (prevBtn) prevBtn.addEventListener('click', () => { if (currentPage > 1) { currentPage -= 1; loadData(); } });
  const nextBtn = document.getElementById('nextPage');
  if (nextBtn) nextBtn.addEventListener('click', () => { if (currentPage < totalPages) { currentPage += 1; loadData(); } });

  // --- REALTIME UPDATES VIA SOCKET.IO ---
  try {
    if (window.io) {
      const socket = window.io('http://127.0.0.1:5001', { transports: ['websocket', 'polling'] });
      socket.on('connect', () => {
        // console.log('Socket connected');
      });
      socket.on('bills_updated', (payload) => {
        // Refresh data when any bill is created/updated/deleted
        loadData();
      });
      socket.on('disconnect', () => {
        // console.log('Socket disconnected');
      });
    }
  } catch (e) {
    console.warn('Socket.IO not available:', e);
  }

  loadData();
});