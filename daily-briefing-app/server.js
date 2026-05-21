const express = require('express');
const cors = require('cors');
const YahooFinance = require('yahoo-finance2').default;
const yahooFinance = new YahooFinance();
const path = require('path');

const app = express();
app.use(cors());
app.use(express.static(path.join(__dirname, 'public')));

const PORT = process.env.PORT || 3000;

app.get('/api/market-data', async (req, res) => {
    try {
        const symbols = [
            '^GSPC', '^NDX', '^DJI', // Indices (S&P 500, Nasdaq 100, Dow Jones)
            'ES=F', 'NQ=F', // Futures
            '^VIX', // VIX
            '^TNX', '^TYX', 'ZT=F', // 10Y, 30Y, 2Y treasuries futures
            // Sectors (XLK, XLV, XLF, XLY, etc.)
            'XLK', 'XLV', 'XLF', 'XLY', 'XLC', 'XLI', 'XLP', 'XLE', 'XLU', 'XLRE', 'XLB'
        ];

        // Fetch quotes individually or in batches to avoid rate limits
        const results = [];
        for (let i = 0; i < symbols.length; i += 5) {
            const batch = symbols.slice(i, i + 5);
            try {
                const batchResults = await Promise.all(batch.map(symbol => yahooFinance.quote(symbol)));
                results.push(...batchResults);
            } catch (err) {
                 console.error(`Error fetching batch ${batch}:`, err);
            }
        }
        res.json(results);
    } catch (error) {
        console.error(error);
        res.status(500).json({ error: 'Failed to fetch market data' });
    }
});

app.get('/api/news', async (req, res) => {
    try {
        const query = req.query.q || 'stock market breaking';
        const results = await yahooFinance.search(query, { newsCount: 15 });
        // filter out news without links or titles
        const validNews = results.news.filter(n => n.link && n.title);
        res.json(validNews.slice(0, 10));
    } catch (error) {
        console.error(error);
        res.status(500).json({ error: 'Failed to fetch news' });
    }
});

// Calculate important levels based on high, low, close of previous day
function calculatePivotPoints(high, low, close) {
    if (!high || !low || !close) return null;
    const pivot = (high + low + close) / 3;
    const r1 = (2 * pivot) - low;
    const s1 = (2 * pivot) - high;
    const r2 = pivot + (high - low);
    const s2 = pivot - (high - low);
    return {
        pivot: pivot.toFixed(2),
        r1: r1.toFixed(2),
        s1: s1.toFixed(2),
        r2: r2.toFixed(2),
        s2: s2.toFixed(2)
    };
}

app.get('/api/analysis', async (req, res) => {
    try {
        // Fetch components for SPY to find top stocks per sector
        // XLK (Tech), XLF (Financials), XLV (Healthcare)
        const sectors = ['AAPL', 'MSFT', 'NVDA', 'JPM', 'BAC', 'JNJ', 'UNH', 'XOM', 'CVX', 'PG'];

        const results = [];
        for (let i = 0; i < sectors.length; i += 5) {
            const batch = sectors.slice(i, i + 5);
            try {
                const batchResults = await Promise.all(batch.map(symbol => yahooFinance.quote(symbol)));
                results.push(...batchResults);
            } catch (err) {
                 console.error(`Error fetching batch ${batch}:`, err);
            }
        }

        const topStocks = results.map(q => {
             const pivots = calculatePivotPoints(q.regularMarketDayHigh, q.regularMarketDayLow, q.regularMarketPreviousClose);
             return {
                 symbol: q.symbol,
                 name: q.shortName,
                 price: q.regularMarketPrice,
                 changePercent: q.regularMarketChangePercent,
                 pivots
             };
        });

        // Oversea markets
        const overseasSymbols = ['^N225', '^FTSE', '^HSI']; // Nikkei, FTSE, Hang Seng
        const overseasResults = await Promise.all(overseasSymbols.map(s => yahooFinance.quote(s).catch(() => null)));

        res.json({
            topStocks,
            overseas: overseasResults.filter(Boolean).map(q => ({ symbol: q.symbol, changePercent: q.regularMarketChangePercent }))
        });

    } catch (error) {
        console.error(error);
        res.status(500).json({ error: 'Failed to fetch analysis data' });
    }
});


app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});
