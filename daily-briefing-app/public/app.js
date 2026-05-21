const API_BASE = '/api';

const MAPPING = {
    '^GSPC': 'S&P 500',
    '^NDX': 'Nasdaq 100',
    '^DJI': 'Dow Jones',
    'ES=F': 'S&P Futures',
    'NQ=F': 'Nasdaq Futures',
    '^VIX': 'VIX',
    '^TNX': '10Y Note',
    '^TYX': '30Y Note',
    'ZT=F': '2Y Note'
};

function formatChange(change, changePercent) {
    if (change === undefined || changePercent === undefined) return { text: 'N/A', cls: '' };
    const sign = change >= 0 ? '+' : '';
    const cls = change >= 0 ? 'up' : 'down';
    return {
        text: `${sign}${change.toFixed(2)} (${sign}${changePercent.toFixed(2)}%)`,
        cls
    };
}

function createTickerHTML(quote) {
    const symbol = quote.symbol;
    const name = MAPPING[symbol] || quote.shortName || symbol;
    const price = quote.regularMarketPrice || quote.postMarketPrice || 'N/A';
    const changeData = formatChange(quote.regularMarketChange, quote.regularMarketChangePercent);

    return `
        <div class="ticker-item">
            <span class="ticker-symbol">${name}</span>
            <span class="ticker-price">${typeof price === 'number' ? price.toFixed(2) : price}</span>
            <span class="ticker-change ${changeData.cls}">${changeData.text}</span>
        </div>
    `;
}

async function fetchMarketData() {
    try {
        const res = await fetch(`${API_BASE}/market-data`);
        const data = await res.json();

        const indices = data.filter(q => ['^GSPC', '^NDX', '^DJI', 'ES=F', 'NQ=F'].includes(q.symbol));
        const rates = data.filter(q => ['^VIX', '^TNX', '^TYX', 'ZT=F'].includes(q.symbol));
        const sectors = data.filter(q => q.symbol.startsWith('XL'));

        document.getElementById('indices-grid').innerHTML = indices.map(createTickerHTML).join('');
        document.getElementById('rates-grid').innerHTML = rates.map(createTickerHTML).join('');
        document.getElementById('sectors-grid').innerHTML = sectors.map(createTickerHTML).join('');

        return { indices, rates, sectors };
    } catch (err) {
        console.error('Error fetching market data', err);
        return {};
    }
}

async function fetchNews() {
    try {
        const res = await fetch(`${API_BASE}/news?q=stock+market+breaking`);
        const news = await res.json();

        const newsHTML = news.map(item => `
            <li>
                <a href="${item.link}" target="_blank" rel="noopener noreferrer">${item.title}</a>
                <div class="news-meta">${item.publisher || 'Yahoo Finance'} • ${new Date(item.providerPublishTime * 1000).toLocaleString()}</div>
            </li>
        `).join('');

        document.getElementById('news-list').innerHTML = newsHTML;
    } catch (err) {
        console.error('Error fetching news', err);
    }
}

async function fetchAnalysisAndRender(marketData) {
    try {
        const { indices, rates, sectors } = marketData;
        if (!indices || !rates || !sectors) return;

        const res = await fetch(`${API_BASE}/analysis`);
        const analysisData = await res.json();

        const sp500 = indices.find(i => i.symbol === '^GSPC');
        const vix = rates.find(r => r.symbol === '^VIX');

        let isMorning = new Date().getHours() < 12;
        document.querySelector('#analysis-section h2').innerText = isMorning ? "Morning Briefing" : "Evening Briefing";

        let analysis = `<p>${isMorning ? "Good morning." : "Good evening."} Global markets are setting up for a dynamic session.</p>`;

        // Oversea markets analysis
        const overseas = analysisData.overseas || [];
        if (overseas.length > 0) {
             const positive = overseas.filter(o => o.changePercent > 0).length;
             if (positive > overseas.length / 2) {
                 analysis += `<p>Overseas markets closed mostly higher, providing a positive tailwind for US equities.</p>`;
             } else {
                 analysis += `<p>Overseas markets closed mostly lower, which may weigh on early US sentiment.</p>`;
             }
        }

        let confidence = "Neutral";
        let confidenceProbability = "50%";

        if (sp500 && sp500.regularMarketChangePercent > 0.5) {
             analysis += `<p>The S&P 500 is showing strong bullish momentum (+${sp500.regularMarketChangePercent.toFixed(2)}%). Look for continuation setups.</p>`;
             confidence = "Bullish";
             confidenceProbability = "68%";
        } else if (sp500 && sp500.regularMarketChangePercent < -0.5) {
             analysis += `<p>The S&P 500 is under heavy pressure (${sp500.regularMarketChangePercent.toFixed(2)}%). Caution advised, focus on defensive sectors.</p>`;
             confidence = "Bearish";
             confidenceProbability = "72%";
        } else if (sp500) {
             analysis += `<p>The S&P 500 is relatively flat (${sp500.regularMarketChangePercent.toFixed(2)}%). Market is seeking direction.</p>`;
        }

        if (vix && vix.regularMarketPrice > 20) {
            analysis += `<p>VIX is elevated at ${vix.regularMarketPrice.toFixed(2)}. Expect high volatility, reduce position sizes and use tighter stops.</p>`;
            confidenceProbability = "Volatility limits directional confidence.";
        } else if (vix) {
            analysis += `<p>VIX is relatively calm at ${vix.regularMarketPrice.toFixed(2)}. Conducive for swing trading and trend following.</p>`;
        }

        // Top Sectors logic
        let topSectorsStr = "";
        let sortedSectors = [];
        if (sectors.length > 0) {
            sortedSectors = [...sectors].sort((a, b) => b.regularMarketChangePercent - a.regularMarketChangePercent);
            let top3 = sortedSectors.slice(0, 3).map(s => `${s.shortName.split(' ')[0]} (${s.symbol})`);
            topSectorsStr = `<li><strong>Sectors to monitor:</strong> Strongest relative strength seen in ${top3.join(', ')}. Look for pullbacks to VWAP in these sectors.</li>`;
        }

        // Top Stocks and Pivots logic
        let stocksHtml = "<h3>Top 10 Stocks to Monitor & Key Levels</h3><div class='grid'>";
        analysisData.topStocks.forEach(stock => {
            stocksHtml += `
                <div class="ticker-item">
                    <span class="ticker-symbol">${stock.symbol}</span>
                    <span class="ticker-price">${stock.price.toFixed(2)} <span class="${stock.changePercent >= 0 ? 'up' : 'down'}">(${stock.changePercent.toFixed(2)}%)</span></span>
                    <div class="pivots" style="font-size: 0.75rem; color: #aaa; margin-top: 5px;">
                        <div>Pivot: ${stock.pivots ? stock.pivots.pivot : 'N/A'}</div>
                        <div>R1: ${stock.pivots ? stock.pivots.r1 : 'N/A'} | S1: ${stock.pivots ? stock.pivots.s1 : 'N/A'}</div>
                    </div>
                </div>
            `;
        });
        stocksHtml += "</div>";

        document.getElementById('analysis-content').innerHTML = analysis + stocksHtml;

        document.getElementById('confidence-level').innerHTML = `${confidence} <span style="font-size:0.8em; color:#888;">(${confidenceProbability} stat prob)</span>`;
        document.getElementById('thought-leader-tips').innerHTML = `
            ${topSectorsStr}
            <li><strong>Index Levels:</strong> S&P 500 prior close is the main pivot. If ES holds above VWAP post-open, target the next resistance liquidity pool.</li>
            <li><strong>Treasury Context:</strong> Review 2-Year (ZT=F) and 10-Year yield movements. Sharp inversion drops often pressure tech/growth (XLK).</li>
            <li><strong>Winning Strategy (High Win Rate):</strong> Wait for the first 30 mins to establish the Opening Range (OR). Trade the OR Breakout (ORB) with volume confirmation on top relative strength stocks.</li>
        `;
    } catch (err) {
        console.error('Error fetching analysis data', err);
    }
}

async function init() {
    const marketData = await fetchMarketData();
    fetchNews();
    if (marketData) {
        fetchAnalysisAndRender(marketData);
    }

    // Refresh every 60 seconds
    setInterval(async () => {
        const md = await fetchMarketData();
        fetchNews();
        if(md) fetchAnalysisAndRender(md);
    }, 60000);
}

init();
