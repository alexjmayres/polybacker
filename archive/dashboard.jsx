import React, { useState, useEffect } from 'react';
import { Activity, TrendingUp, DollarSign, Zap, Play, Pause, Settings, Eye, AlertCircle, CheckCircle2, XCircle, BarChart3, Target, Clock } from 'lucide-react';

export default function PolymarketDashboard() {
  const [botStatus, setBotStatus] = useState('stopped');
  const [stats, setStats] = useState({
    totalProfit: 0,
    tradesExecuted: 0,
    winRate: 0,
    opportunitiesFound: 0,
    avgProfit: 0,
    runtime: '0h 0m'
  });
  
  const [currentOpportunities, setCurrentOpportunities] = useState([]);
  const [recentTrades, setRecentTrades] = useState([]);
  const [config, setConfig] = useState({
    minProfit: 1.0,
    tradeAmount: 10,
    pollInterval: 30
  });
  
  const [showSettings, setShowSettings] = useState(false);
  const [liveLog, setLiveLog] = useState([]);

  // Simulate real-time updates (in production, this would connect to your Python backend via WebSocket)
  useEffect(() => {
    if (botStatus === 'running') {
      const interval = setInterval(() => {
        // Simulate finding opportunities
        if (Math.random() > 0.7) {
          const newOpp = {
            id: Date.now(),
            market: 'Sample Market',
            yesPrice: (0.45 + Math.random() * 0.1).toFixed(4),
            noPrice: (0.47 + Math.random() * 0.08).toFixed(4),
            profit: (0.01 + Math.random() * 0.02).toFixed(4),
            profitPct: ((0.01 + Math.random() * 0.02) * 100).toFixed(2)
          };
          setCurrentOpportunities(prev => [newOpp, ...prev].slice(0, 5));
          
          // Add log entry
          addLog(`Found arbitrage: ${newOpp.profitPct}% profit opportunity`, 'success');
        }
        
        // Simulate stats update
        setStats(prev => ({
          ...prev,
          totalProfit: prev.totalProfit + (Math.random() * 2),
          tradesExecuted: prev.tradesExecuted + (Math.random() > 0.8 ? 1 : 0),
          opportunitiesFound: prev.opportunitiesFound + (Math.random() > 0.7 ? 1 : 0)
        }));
      }, 3000);
      
      return () => clearInterval(interval);
    }
  }, [botStatus]);

  const addLog = (message, type = 'info') => {
    setLiveLog(prev => [{
      message,
      type,
      time: new Date().toLocaleTimeString()
    }, ...prev].slice(0, 50));
  };

  const toggleBot = () => {
    if (botStatus === 'running') {
      setBotStatus('stopped');
      addLog('Bot stopped', 'warning');
    } else {
      setBotStatus('running');
      addLog('Bot started - Scanning markets...', 'success');
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-indigo-950 to-slate-900 text-white font-sans">
      {/* Animated background effects */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-1/2 -left-1/2 w-full h-full bg-gradient-to-br from-indigo-500/10 to-transparent rounded-full blur-3xl animate-pulse" />
        <div className="absolute -bottom-1/2 -right-1/2 w-full h-full bg-gradient-to-tl from-violet-500/10 to-transparent rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
      </div>

      <div className="relative z-10">
        {/* Header */}
        <header className="border-b border-white/10 backdrop-blur-xl bg-white/5">
          <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-violet-500 rounded-lg flex items-center justify-center">
                <TrendingUp className="w-6 h-6" />
              </div>
              <div>
                <h1 className="text-xl font-bold tracking-tight">Polymarket Arbitrage Bot</h1>
                <p className="text-xs text-gray-400">Real-time profit automation</p>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowSettings(!showSettings)}
                className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 transition-all flex items-center gap-2"
              >
                <Settings className="w-4 h-4" />
                Settings
              </button>
              
              <button
                onClick={toggleBot}
                className={`px-6 py-2 rounded-lg font-semibold transition-all flex items-center gap-2 shadow-lg ${
                  botStatus === 'running'
                    ? 'bg-red-500 hover:bg-red-600 shadow-red-500/50'
                    : 'bg-gradient-to-r from-indigo-500 to-violet-500 hover:from-indigo-600 hover:to-violet-600 shadow-indigo-500/50'
                }`}
              >
                {botStatus === 'running' ? (
                  <>
                    <Pause className="w-4 h-4" />
                    Stop Bot
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    Start Bot
                  </>
                )}
              </button>
            </div>
          </div>
        </header>

        <main className="max-w-7xl mx-auto px-6 py-8">
          {/* Status Banner */}
          <div className={`mb-8 p-4 rounded-xl border backdrop-blur-sm transition-all ${
            botStatus === 'running'
              ? 'bg-green-500/10 border-green-500/30'
              : 'bg-amber-500/10 border-amber-500/30'
          }`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-3 h-3 rounded-full ${
                  botStatus === 'running' ? 'bg-green-500 animate-pulse' : 'bg-amber-500'
                }`} />
                <span className="font-medium">
                  {botStatus === 'running' ? 'Bot is actively scanning markets' : 'Bot is stopped'}
                </span>
              </div>
              {botStatus === 'running' && (
                <div className="flex items-center gap-2 text-sm text-gray-400">
                  <Clock className="w-4 h-4" />
                  Next scan in {config.pollInterval}s
                </div>
              )}
            </div>
          </div>

          {/* Settings Modal */}
          {showSettings && (
            <div className="mb-8 p-6 rounded-xl bg-white/5 border border-white/10 backdrop-blur-xl">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Settings className="w-5 h-5" />
                Bot Configuration
              </h3>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-2">Min Profit Threshold (%)</label>
                  <input
                    type="number"
                    value={config.minProfit}
                    onChange={(e) => setConfig({...config, minProfit: parseFloat(e.target.value)})}
                    className="w-full px-4 py-2 rounded-lg bg-white/5 border border-white/10 focus:border-indigo-500 focus:outline-none"
                    step="0.1"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-2">Trade Amount (USDC)</label>
                  <input
                    type="number"
                    value={config.tradeAmount}
                    onChange={(e) => setConfig({...config, tradeAmount: parseFloat(e.target.value)})}
                    className="w-full px-4 py-2 rounded-lg bg-white/5 border border-white/10 focus:border-indigo-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-2">Poll Interval (seconds)</label>
                  <input
                    type="number"
                    value={config.pollInterval}
                    onChange={(e) => setConfig({...config, pollInterval: parseInt(e.target.value)})}
                    className="w-full px-4 py-2 rounded-lg bg-white/5 border border-white/10 focus:border-indigo-500 focus:outline-none"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Stats Grid */}
          <div className="grid grid-cols-4 gap-4 mb-8">
            <StatCard
              icon={<DollarSign className="w-6 h-6" />}
              label="Total Profit"
              value={`$${stats.totalProfit.toFixed(2)}`}
              trend="+12.3%"
              color="green"
            />
            <StatCard
              icon={<Target className="w-6 h-6" />}
              label="Trades Executed"
              value={stats.tradesExecuted}
              trend={`${stats.opportunitiesFound} opportunities`}
              color="blue"
            />
            <StatCard
              icon={<Zap className="w-6 h-6" />}
              label="Avg Profit/Trade"
              value={stats.tradesExecuted > 0 ? `$${(stats.totalProfit / stats.tradesExecuted).toFixed(2)}` : '$0.00'}
              trend="Per trade"
              color="violet"
            />
            <StatCard
              icon={<Activity className="w-6 h-6" />}
              label="Runtime"
              value={stats.runtime}
              trend="Uptime"
              color="indigo"
            />
          </div>

          {/* Main Content Grid */}
          <div className="grid grid-cols-3 gap-6">
            {/* Live Opportunities */}
            <div className="col-span-2">
              <div className="rounded-xl bg-white/5 border border-white/10 backdrop-blur-xl overflow-hidden">
                <div className="p-4 border-b border-white/10 flex items-center justify-between">
                  <h3 className="font-semibold flex items-center gap-2">
                    <Eye className="w-5 h-5 text-indigo-400" />
                    Live Arbitrage Opportunities
                  </h3>
                  <span className="text-xs bg-indigo-500/20 text-indigo-300 px-2 py-1 rounded">
                    {currentOpportunities.length} Active
                  </span>
                </div>
                
                <div className="divide-y divide-white/5 max-h-96 overflow-y-auto">
                  {currentOpportunities.length === 0 ? (
                    <div className="p-8 text-center text-gray-500">
                      <AlertCircle className="w-12 h-12 mx-auto mb-3 opacity-50" />
                      <p>No opportunities found yet</p>
                      <p className="text-sm mt-1">The bot will alert you when arbitrage is detected</p>
                    </div>
                  ) : (
                    currentOpportunities.map((opp) => (
                      <div key={opp.id} className="p-4 hover:bg-white/5 transition-colors">
                        <div className="flex items-center justify-between mb-2">
                          <span className="font-medium text-sm">Market Opportunity</span>
                          <span className="text-green-400 font-bold">{opp.profitPct}% profit</span>
                        </div>
                        <div className="grid grid-cols-3 gap-4 text-sm">
                          <div>
                            <span className="text-gray-400 block">YES Price</span>
                            <span className="text-white">${opp.yesPrice}</span>
                          </div>
                          <div>
                            <span className="text-gray-400 block">NO Price</span>
                            <span className="text-white">${opp.noPrice}</span>
                          </div>
                          <div>
                            <span className="text-gray-400 block">Profit</span>
                            <span className="text-green-400">${opp.profit}</span>
                          </div>
                        </div>
                        <button className="mt-3 w-full py-2 bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 rounded-lg text-sm font-medium transition-all">
                          Execute Trade
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Recent Trades */}
              <div className="mt-6 rounded-xl bg-white/5 border border-white/10 backdrop-blur-xl overflow-hidden">
                <div className="p-4 border-b border-white/10">
                  <h3 className="font-semibold flex items-center gap-2">
                    <BarChart3 className="w-5 h-5 text-violet-400" />
                    Recent Trades
                  </h3>
                </div>
                <div className="p-4">
                  <div className="space-y-3">
                    {[1, 2, 3].map((i) => (
                      <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-white/5">
                        <div className="flex items-center gap-3">
                          <CheckCircle2 className="w-5 h-5 text-green-400" />
                          <div>
                            <div className="text-sm font-medium">Arbitrage Trade #{i}</div>
                            <div className="text-xs text-gray-400">2 minutes ago</div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-green-400 font-semibold">+$0.{30 + i}2</div>
                          <div className="text-xs text-gray-400">{2.1 + i}% return</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Live Activity Log */}
            <div className="rounded-xl bg-white/5 border border-white/10 backdrop-blur-xl overflow-hidden">
              <div className="p-4 border-b border-white/10">
                <h3 className="font-semibold flex items-center gap-2">
                  <Activity className="w-5 h-5 text-green-400" />
                  Live Activity Log
                </h3>
              </div>
              <div className="p-3 max-h-[600px] overflow-y-auto space-y-2">
                {liveLog.length === 0 ? (
                  <div className="text-center text-gray-500 py-8">
                    <p className="text-sm">No activity yet</p>
                  </div>
                ) : (
                  liveLog.map((log, i) => (
                    <div key={i} className="text-xs p-2 rounded bg-white/5 border-l-2 border-indigo-500">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-gray-500">{log.time}</span>
                        {log.type === 'success' && <CheckCircle2 className="w-3 h-3 text-green-400" />}
                        {log.type === 'warning' && <AlertCircle className="w-3 h-3 text-amber-400" />}
                        {log.type === 'error' && <XCircle className="w-3 h-3 text-red-400" />}
                      </div>
                      <div className="text-gray-300">{log.message}</div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </main>
      </div>

      {/* Custom styles for animations */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        * {
          font-family: 'Inter', sans-serif;
        }
        
        @keyframes pulse {
          0%, 100% { opacity: 0.6; }
          50% { opacity: 0.3; }
        }
        
        .animate-pulse {
          animation: pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }
        
        /* Custom scrollbar */
        ::-webkit-scrollbar {
          width: 6px;
        }
        
        ::-webkit-scrollbar-track {
          background: rgba(255, 255, 255, 0.05);
        }
        
        ::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.2);
          border-radius: 3px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
          background: rgba(255, 255, 255, 0.3);
        }
      `}</style>
    </div>
  );
}

function StatCard({ icon, label, value, trend, color }) {
  const colorClasses = {
    green: 'from-green-500 to-emerald-500',
    blue: 'from-blue-500 to-cyan-500',
    violet: 'from-violet-500 to-purple-500',
    indigo: 'from-indigo-500 to-blue-500'
  };

  return (
    <div className="rounded-xl bg-white/5 border border-white/10 backdrop-blur-xl p-5 hover:bg-white/10 transition-all group">
      <div className="flex items-start justify-between mb-3">
        <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${colorClasses[color]} flex items-center justify-center group-hover:scale-110 transition-transform`}>
          {icon}
        </div>
      </div>
      <div className="text-2xl font-bold mb-1">{value}</div>
      <div className="text-sm text-gray-400">{label}</div>
      <div className="text-xs text-gray-500 mt-1">{trend}</div>
    </div>
  );
}