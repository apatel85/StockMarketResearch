const YahooFinance = require('yahoo-finance2').default;
const yahooFinance = new YahooFinance();
yahooFinance.quote('ZT=F').then(console.log).catch(console.error);
yahooFinance.quote('^IRX').then(console.log).catch(console.error);
