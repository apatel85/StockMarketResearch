const YahooFinance = require('yahoo-finance2').default;
const yahooFinance = new YahooFinance();
yahooFinance.quote('AAPL').then(console.log).catch(console.error);
