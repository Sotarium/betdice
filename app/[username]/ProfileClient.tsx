'use client';

import { useEffect, useMemo, useRef, useState } from 'react';

const DEFAULT_AVATAR = 'https://rollbux.com/icons/token.png';
const BUX_TO_USD = 0.002;
const EMPTY_STATE = { 
  total_earnings_bux: 0, 
  total_earnings_usd: 0, 
  earnings_24h_bux: 0, 
  earnings_24h_usd: 0, 
  current_balance_bux: 0, 
  history: [], 
  chart_points: [0, 0], 
  chart_labels: ['7:00 PM', '8:00 PM'] 
};

function buxToUsd(value: any) { return (Number(value) || 0) * BUX_TO_USD; }
function ageMs(item: any) { return Date.now() - (Number(item.timestamp_ms) || Date.now()); }

function formatDate(item: any) {
  if (item.when) {
    const [date, time] = String(item.when).split(',');
    const bits = String(date || '').trim().split('/');
    if (bits.length === 3) return { 
      date: `${bits[2].length === 2 ? '20' : ''}${bits[2]}/${bits[0].padStart(2, '0')}/${bits[1].padStart(2, '0')}`, 
      time: (time || item.time || '07:00 PM').trim() 
    };
  }
  const dt = item.timestamp_ms ? new Date(item.timestamp_ms) : new Date();
  return { 
    date: `${dt.getFullYear()}/${String(dt.getMonth() + 1).padStart(2, '0')}/${String(dt.getDate()).padStart(2, '0')}`, 
    time: dt.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) 
  };
}

function amount(item: any) {
  const bux = Number(item.amount_bux) || (Number(item.amount_usd) / BUX_TO_USD);
  return `$${buxToUsd(bux).toFixed(2)}`;
}

export default function Dashboard({ username }: { username?: string }) {
  const [timeRange, setTimeRange] = useState('24H');
  const [hoverData, setHoverData] = useState<{ value: number; label: string } | null>(null);
  const [data, setData] = useState<any>(EMPTY_STATE);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const chartRef = useRef<any>(null);
  const safeUser = username || 'sotarium';

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const response = await fetch(`/api/users?user=${encodeURIComponent(safeUser)}`, { cache: 'no-store' });
        if (response.ok && alive) setData(await response.json());
      } catch {}
    };
    load();
    const timer = setInterval(load, 3500);
    return () => { alive = false; clearInterval(timer); };
  }, [safeUser]);

  const history = Array.isArray(data.history) ? data.history : [];
  const totalBux = Number(data.total_earnings_bux) || (Number(data.total_earnings_usd) / BUX_TO_USD);
  const totalUsd = Number(data.total_earnings_usd) || buxToUsd(totalBux);
  
  const rangeMs = (timeRange === '24H' || timeRange === '1D') ? 86400000 
    : (timeRange === '7D' || timeRange === '1W') ? 86400000 * 7 
    : (timeRange === '30D' || timeRange === '1M') ? 86400000 * 30 
    : Infinity;

  const inRange = useMemo(() => history.filter((item: any) => ageMs(item) <= rangeMs), [history, rangeMs]);
  const rangeBux = inRange.reduce((sum: number, item: any) => sum + (Number(item.amount_bux) || (Number(item.amount_usd) / BUX_TO_USD)), 0);
  const rangeUsd = buxToUsd(rangeBux);

  const points = useMemo(() => {
    if (!inRange.length) return { labels: data.chart_labels || ['7:00 PM', '8:00 PM'], values: data.chart_points || [0, 0] };
    let total = 0;
    const labels = ['6:00 PM'];
    const values = [0];
    [...inRange].sort((a: any, b: any) => (a.timestamp_ms || 0) - (b.timestamp_ms || 0)).forEach((item: any) => {
      total += Number(item.amount_bux) || (Number(item.amount_usd) / BUX_TO_USD);
      labels.push(item.time || formatDate(item).time);
      values.push(Number(buxToUsd(total).toFixed(2)));
    });
    return { labels, values };
  }, [inRange, data.chart_labels, data.chart_points]);

  // Interactive Chart.js setup
  useEffect(() => {
    let disposed = false;
    let canvasEl: HTMLCanvasElement | null = null;
    let handleMouseLeave: (() => void) | null = null;

    import('chart.js/auto').then(({ default: Chart }) => {
      if (disposed || !canvasRef.current) return;
      chartRef.current?.destroy();

      const crosshairPlugin = {
        id: 'fomoCrosshair',
        afterDraw(chart: any) {
          const activeElements = chart.getActiveElements();
          if (activeElements && activeElements.length > 0) {
            const activePoint = activeElements[0];
            const ctx = chart.ctx;
            const x = activePoint.element.x;
            const topY = chart.chartArea.top;
            const bottomY = chart.chartArea.bottom;

            ctx.save();
            ctx.beginPath();
            ctx.moveTo(x, topY);
            ctx.lineTo(x, bottomY);
            ctx.lineWidth = 1;
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
            ctx.setLineDash([3, 3]);
            ctx.stroke();
            ctx.restore();
          }
        }
      };

      chartRef.current = new Chart(canvasRef.current, {
        type: 'line',
        data: {
          labels: points.labels,
          datasets: [{
            data: points.values,
            borderColor: '#22c55e',
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 5,
            pointHoverBackgroundColor: '#22c55e',
            pointHoverBorderColor: '#ffffff',
            pointHoverBorderWidth: 2,
            fill: 'start',
            tension: 0.4,
            cubicInterpolationMode: 'monotone',
            backgroundColor: 'rgba(34, 197, 94, 0.16)'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          interaction: { mode: 'index', intersect: false },
          onHover: (event: any, activeElements: any) => {
            if (activeElements && activeElements.length > 0) {
              const idx = activeElements[0].index;
              setHoverData({ value: points.values[idx] ?? 0, label: points.labels[idx] ?? '' });
            } else {
              setHoverData(null);
            }
          },
          plugins: { legend: { display: false }, tooltip: { enabled: false } },
          scales: { x: { display: false }, y: { display: false, suggestedMin: 0 } }
        },
        plugins: [crosshairPlugin]
      });

      canvasEl = canvasRef.current;
      handleMouseLeave = () => {
        setHoverData(null);
        if (chartRef.current) {
          chartRef.current.setActiveElements([]);
          chartRef.current.render();
        }
      };
      if (canvasEl) canvasEl.addEventListener('mouseleave', handleMouseLeave);
    });

    return () => {
      disposed = true;
      if (canvasEl && handleMouseLeave) canvasEl.removeEventListener('mouseleave', handleMouseLeave);
      chartRef.current?.destroy();
    };
  }, [points]);

  // Top 5 biggest payouts
  const displayedPayouts = useMemo(() => {
    return [...history]
      .sort((a: any, b: any) => (Number(b.amount_bux) || 0) - (Number(a.amount_bux) || 0))
      .slice(0, 5);
  }, [history]);

  // All rains list (latest first)
  const displayedRain = useMemo(() => {
    return [...history].sort((a: any, b: any) => (b.timestamp_ms || 0) - (a.timestamp_ms || 0));
  }, [history]);

  const money = `$${totalUsd.toFixed(2)}`;
  const splitMoney = { 
    main: `$${Math.floor(totalUsd).toLocaleString()}`, 
    sub: `.${String(Math.round((totalUsd % 1) * 100)).padStart(2, '0')}` 
  };

  const row = (item: any, index: number) => { 
    const date = formatDate(item); 
    return (
      <div className="modern-board-row" key={`${item.timestamp_ms || index}-${index}`}>
        <div className="board-col-player">
          <div className="board-avatar-box"><span>♙</span></div>
          <span className="board-player-name">Rain {history.length - history.indexOf(item)}</span>
        </div>
        <div className="board-col-date">
          <span className="board-date-main">{date.date}</span>
          <span className="board-date-sub">{date.time}</span>
        </div>
        <div className="board-col-payout">
          <span className="board-num-val">{amount(item)}</span>
        </div>
      </div>
    ); 
  };

  return (
    <div className="fomo-page">
      {/* User Header */}
      <div className="fomo-profile-row" style={{ paddingTop: '24px' }}>
        <div className="fomo-avatar-circle">
          <img className="fomo-avatar-img" src={data.avatar || DEFAULT_AVATAR} alt={safeUser} />
        </div>
        <div className="fomo-user-meta">
          <div className="fomo-user-name">{data.username || safeUser}</div>
          <div className="fomo-user-handle">@{data.username || safeUser}</div>
        </div>
      </div>

      {/* Main Grid */}
      <div className="fomo-grid">
        <div className="fomo-left-col">
          <div className="fomo-chart-header">
            <div className="fomo-balance-box">
              <div className="fomo-balance-val">
                <span className="val-main">{splitMoney.main}</span>
                <span className="val-sub">{splitMoney.sub}</span>
              </div>
              <div className="fomo-balance-sub">
                <span className="pnl-green">
                  {hoverData ? `+$${Number(hoverData.value).toFixed(2)}` : `+$${Math.round(rangeUsd)}`}
                </span>
                <span className="pnl-period">{hoverData ? hoverData.label : (timeRange === '1D' ? '24h' : timeRange.toLowerCase())}</span>
              </div>
            </div>

            {/* Timeframe selector: 24H, 7D, 30D, ALL */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div role="tablist" style={{ position: 'relative', display: 'inline-grid', gridAutoFlow: 'column', gridAutoColumns: '1fr', alignItems: 'center', borderRadius: '8px', padding: '2px', border: '1px solid rgba(255,255,255,0.08)', background: '#090814' }}>
                <div style={{ position: 'absolute', top: '2px', bottom: '2px', borderRadius: '6px', background: '#1d1c2d', border: '1px solid rgba(255,255,255,0.08)', transition: 'all 0.2s ease', left: `calc(${['24H', '7D', '30D', 'ALL'].indexOf(timeRange) * 25}% + 2px)`, width: 'calc(25% - 4px)', zIndex: 1, pointerEvents: 'none' }} />
                {['24H', '7D', '30D', 'ALL'].map(item => (
                  <button key={item} type="button" onClick={() => setTimeRange(item)} style={{ position: 'relative', zIndex: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', minWidth: '36px', padding: '4px 6px', fontSize: '11px', fontWeight: 700, cursor: 'pointer', background: 'transparent', border: 'none', color: timeRange === item ? '#ffffff' : '#717084' }}>
                    {item}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Interactive Chart */}
          <div className="fomo-chart-wrap">
            <canvas ref={canvasRef} id="pnlCanvas" />
          </div>

          {/* Total Cash Card */}
          <div className="fomo-cash-card">
            <div className="glass-round">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 5 10" fill="none">
                <path d="M4.86208 6.6257C4.86208 5.65202 4.20146 4.80474 3.25354 4.56412L1.84576 4.21508C1.5925 4.15091 1.37472 4.00893 1.21333 3.80136C1.05826 3.60546 0.972704 3.35514 0.972704 3.09653C0.972704 2.46118 1.48945 1.94444 2.12479 1.94444H2.73729C3.32451 1.94444 3.81694 2.38586 3.88257 2.97114C3.91271 3.23802 4.15382 3.43098 4.41972 3.39987C4.68659 3.36973 4.87861 3.12912 4.84847 2.86273C4.73375 1.83946 3.90687 1.06409 2.89722 0.987769V0.486111C2.89722 0.21875 2.67847 0 2.41111 0C2.14375 0 1.925 0.21875 1.925 0.486111V0.992635C0.84826 1.09472 0 1.99353 0 3.097C0 3.5729 0.15993 4.03762 0.447221 4.40123C0.735485 4.7731 1.14723 5.04149 1.60854 5.15864L3.01632 5.50762C3.53014 5.6379 3.88889 6.09777 3.88889 6.62617C3.88889 6.93194 3.76833 7.22067 3.54958 7.43942C3.33132 7.65817 3.04257 7.77825 2.73681 7.77825H2.1243C1.53708 7.77825 1.04465 7.33689 0.979024 6.75162C0.948885 6.48474 0.706318 6.29269 0.441873 6.32283C0.174998 6.35297 -0.0170137 6.59364 0.0131252 6.86003C0.126389 7.87017 0.933819 8.63773 1.92549 8.73155V9.23611C1.92549 9.50347 2.14424 9.72222 2.4116 9.72222C2.67896 9.72222 2.89771 9.50347 2.89771 9.23611V8.73445C3.40278 8.69605 3.87479 8.48994 4.23792 8.12681C4.64042 7.72432 4.86208 7.19153 4.86208 6.6257Z" fill="currentColor" />
              </svg>
            </div>
            <div className="fomo-cash-info">
              <div className="fomo-cash-title">Total cash</div>
              <div className="fomo-cash-val">{money}</div>
            </div>
          </div>

          {/* Biggest Payout */}
          <div className="fomo-box fomo-payout-box">
            <div className="fomo-box-header">
              <span className="box-title">Biggest Payout</span>
            </div>
            <div className="fomo-table-cols modern-cols">
              <span className="mcol-player">Rain</span>
              <span className="mcol-date">Date</span>
              <span className="mcol-payout">Payout</span>
            </div>
            <div className="fomo-table-body">
              {displayedPayouts.length ? displayedPayouts.map(row) : <div className="fomo-empty-state">No closed positions</div>}
            </div>
          </div>
        </div>

        {/* Rain History */}
        <div className="fomo-right-col">
          <div className="fomo-box fomo-rain-box">
            <div className="fomo-box-header" style={{ marginBottom: '14px' }}>
              <span className="box-title">Rain History</span>
            </div>
            <div className="fomo-rain-cols modern-cols">
              <span className="mcol-player">Rain</span>
              <span className="mcol-date">Date</span>
              <span className="mcol-payout">Payout</span>
            </div>
            <div className="fomo-rain-body">
              {displayedRain.length ? displayedRain.map(row) : <div className="fomo-empty-state">No Datas yet</div>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
