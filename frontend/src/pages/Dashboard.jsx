import { useState, useEffect, useRef } from 'react';
import { UploadCloud, Database, Zap, ShieldAlert, Cpu } from 'lucide-react';

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const fileInputRef = useRef(null);

  const fetchStats = async () => {
    try {
      const res = await fetch('/analysis/stats');
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  const handleFileChange = async (e) => {
    if (!e.target.files.length) return;
    setIsUploading(true);
    setUploadResult(null);

    const formData = new FormData();
    Array.from(e.target.files).forEach((file) => {
      formData.append('files', file);
    });

    try {
      const res = await fetch('/documents/upload', {
        method: 'POST',
        body: formData,
      });
      if (res.ok) {
        const data = await res.json();
        setUploadResult({ type: 'success', msg: `Successfully uploaded ${data.length} files.` });
        fetchStats();
      } else {
        const err = await res.json();
        setUploadResult({ type: 'error', msg: err.detail || 'Upload failed' });
      }
    } catch (error) {
      setUploadResult({ type: 'error', msg: 'Network error uploading files.' });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleRunAnalysis = async () => {
    setIsAnalyzing(true);
    setAnalysisResult(null);
    try {
      const res = await fetch('/analysis/run?engine=redis', {
        method: 'POST',
      });
      if (res.ok) {
        const data = await res.json();
        setAnalysisResult({ type: 'success', msg: `Analysis complete. Processed ${data.processed} docs, found ${data.pairs_found} pairs (${data.pairs_flagged} flagged).` });
        fetchStats();
      } else {
        const err = await res.json();
        setAnalysisResult({ type: 'error', msg: err.detail || 'Analysis failed' });
      }
    } catch (error) {
      setAnalysisResult({ type: 'error', msg: 'Network error running analysis.' });
    } finally {
      setIsAnalyzing(false);
    }
  };

  const StatCard = ({ title, value, icon: Icon, colorClass }) => (
    <div className="glass-panel p-6 flex items-start gap-4 hover:shadow-2xl transition-all duration-300">
      <div className={`p-3 rounded-xl ${colorClass} bg-opacity-10 backdrop-blur-md`}>
        <Icon className={`w-6 h-6 ${colorClass.replace('bg-', 'text-')}`} />
      </div>
      <div>
        <p className="text-sm font-medium text-slate-400 mb-1">{title}</p>
        <h3 className="text-3xl font-bold text-white tracking-tight">{value ?? '-'}</h3>
      </div>
    </div>
  );

  return (
    <div className="space-y-8 animate-slide-up">
      {/* Header */}
      <div>
        <h1 className="text-4xl font-bold text-white mb-2">Dashboard</h1>
        <p className="text-slate-400">Overview of your document corpus and analysis engine.</p>
      </div>

      {/* Upload Zone */}
      <div className="glass-panel p-8 flex flex-col items-center justify-center border-dashed border-2 border-slate-700/50 hover:border-neon-blue/50 transition-colors relative group">
        <div className="absolute inset-0 bg-linear-to-b from-neon-blue/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity rounded-2xl pointer-events-none" />
        
        <div className="p-4 rounded-full bg-slate-800/80 mb-4 group-hover:scale-110 transition-transform duration-300 shadow-[0_0_20px_rgba(59,130,246,0.15)]">
          <UploadCloud className="w-8 h-8 text-neon-blue" />
        </div>
        <h2 className="text-xl font-semibold text-white mb-2">Upload Documents</h2>
        <p className="text-sm text-slate-400 mb-6 text-center max-w-md">
          Select multiple files (text or code) to add them to the corpus. They will be automatically shingled and MinHashed.
        </p>
        
        <input 
          type="file" 
          multiple 
          className="hidden" 
          ref={fileInputRef}
          onChange={handleFileChange}
        />
        
        <div className="flex gap-4">
          <button 
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="glass-button px-6 py-2.5 text-white font-medium shadow-[0_0_15px_rgba(59,130,246,0.2)] hover:shadow-[0_0_25px_rgba(59,130,246,0.4)]"
          >
            {isUploading ? 'Uploading...' : 'Browse Files'}
          </button>

          <button 
            onClick={handleRunAnalysis}
            disabled={isAnalyzing}
            className="glass-button px-6 py-2.5 text-white font-medium bg-neon-purple/20 border-neon-purple/50 shadow-[0_0_15px_rgba(168,85,247,0.2)] hover:shadow-[0_0_25px_rgba(168,85,247,0.4)] hover:bg-neon-purple/30"
          >
            {isAnalyzing ? 'Analyzing...' : 'Run Analysis'}
          </button>
        </div>

        {(uploadResult || analysisResult) && (
          <div className="mt-4 flex flex-col gap-2">
            {uploadResult && (
              <div className={`px-4 py-2 rounded-lg text-sm font-medium ${
                uploadResult.type === 'success' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'
              }`}>
                {uploadResult.msg}
              </div>
            )}
            {analysisResult && (
              <div className={`px-4 py-2 rounded-lg text-sm font-medium ${
                analysisResult.type === 'success' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'
              }`}>
                {analysisResult.msg}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard 
          title="Total Documents" 
          value={stats?.total_documents} 
          icon={Database} 
          colorClass="bg-neon-blue text-neon-blue"
        />
        <StatCard 
          title="Pairs Analyzed" 
          value={stats?.actual_pairs_compared?.toLocaleString()} 
          icon={Zap} 
          colorClass="bg-neon-cyan text-neon-cyan"
        />
        <StatCard 
          title="Flagged Duplicates" 
          value={stats?.flagged_pairs} 
          icon={ShieldAlert} 
          colorClass="bg-red-400 text-red-400"
        />
        <StatCard 
          title="Comparison Reduction" 
          value={stats?.comparison_reduction_pct ? `${stats.comparison_reduction_pct.toFixed(1)}%` : null} 
          icon={Cpu} 
          colorClass="bg-neon-purple text-neon-purple"
        />
      </div>

      {/* Benchmark Info if available */}
      {stats?.benchmark?.speedup_multiplier && (
        <div className="glass-panel p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Latest Benchmark Results</h3>
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
            <div className="flex-1 space-y-4 w-full">
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-slate-300">Naive (Brute-force) Engine</span>
                  <span className="font-mono text-neon-cyan">{stats.benchmark.naive_duration_seconds?.toFixed(3)}s</span>
                </div>
                <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full bg-neon-cyan transition-all" style={{ width: '100%' }}></div>
                </div>
              </div>
              
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-slate-300">LSH (Redis) Engine</span>
                  <span className="font-mono text-neon-purple">{stats.benchmark.lsh_duration_seconds?.toFixed(3)}s</span>
                </div>
                <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full bg-neon-purple transition-all" style={{ width: `${Math.min(100, (stats.benchmark.lsh_duration_seconds / stats.benchmark.naive_duration_seconds) * 100)}%` }}></div>
                </div>
              </div>
            </div>
            
            <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-700/50 text-center shrink-0">
              <p className="text-sm text-slate-400 mb-1">Lookup Speedup</p>
              <p className="text-2xl font-bold text-white">{stats.benchmark.speedup_multiplier}x</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
