import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight, Search, AlertCircle, FileText, Filter } from 'lucide-react';

export default function Results() {
  const [pairs, setPairs] = useState([]);
  const [loading, setLoading] = useState(true);
  
  const [minSim, setMinSim] = useState(0.5);
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  const fetchPairs = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/analysis/pairs?page=${page}&page_size=20&min_similarity=${minSim}&flagged_only=${flaggedOnly}`);
      if (res.ok) {
        const data = await res.json();
        setPairs(data.pairs);
        setTotal(data.total);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPairs();
  }, [minSim, flaggedOnly, page]);

  return (
    <div className="space-y-6 animate-slide-up">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Similarity Results</h1>
          <p className="text-slate-400">Found {total} pairs matching your criteria.</p>
        </div>
        
        <div className="glass-panel p-2 flex items-center gap-4">
          <div className="flex items-center gap-2 px-3 py-1">
            <Filter className="w-4 h-4 text-slate-400" />
            <label className="text-sm font-medium text-slate-300">Min Similarity:</label>
            <input 
              type="number" 
              step="0.05"
              min="0"
              max="1"
              value={minSim}
              onChange={(e) => { setMinSim(parseFloat(e.target.value) || 0); setPage(1); }}
              className="bg-slate-900 border border-slate-700 text-white rounded px-2 py-1 w-20 text-sm focus:outline-none focus:border-neon-blue"
            />
          </div>
          
          <div className="h-6 w-px bg-slate-700"></div>
          
          <label className="flex items-center gap-2 cursor-pointer px-2">
            <input 
              type="checkbox" 
              checked={flaggedOnly}
              onChange={(e) => { setFlaggedOnly(e.target.checked); setPage(1); }}
              className="accent-red-500 w-4 h-4 rounded"
            />
            <span className="text-sm font-medium text-slate-300">Flagged Only</span>
          </label>
        </div>
      </div>

      <div className="glass-panel overflow-hidden">
        {loading ? (
          <div className="p-12 flex justify-center">
            <div className="w-8 h-8 rounded-full border-2 border-neon-blue border-t-transparent animate-spin"></div>
          </div>
        ) : pairs.length === 0 ? (
          <div className="p-12 text-center text-slate-400">
            <Search className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No similarity pairs found matching the criteria.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-900/50 border-b border-slate-700/50">
                  <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Document A</th>
                  <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Document B</th>
                  <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Estimated LSH</th>
                  <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Exact Jaccard</th>
                  <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Status</th>
                  <th className="px-6 py-4 text-right"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {pairs.map((pair) => (
                  <tr key={pair.id} className="hover:bg-slate-800/30 transition-colors group">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-slate-500" />
                        <span className="text-sm font-medium text-slate-200">{pair.document_a_filename || `Doc ${pair.document_a_id}`}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-slate-500" />
                        <span className="text-sm font-medium text-slate-200">{pair.document_b_filename || `Doc ${pair.document_b_id}`}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-sm text-slate-400">{(pair.estimated_similarity * 100).toFixed(1)}%</span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-sm font-medium text-white">{(pair.exact_similarity * 100).toFixed(1)}%</span>
                    </td>
                    <td className="px-6 py-4">
                      {pair.is_flagged ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20">
                          <AlertCircle className="w-3.5 h-3.5" />
                          Flagged
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-400 border border-slate-700">
                          Normal
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <Link 
                        to={`/pairs/${pair.id}`}
                        className="inline-flex items-center justify-center p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition-colors opacity-0 group-hover:opacity-100"
                      >
                        <ChevronRight className="w-5 h-5" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        
        {/* Pagination Controls */}
        <div className="border-t border-slate-700/50 p-4 flex items-center justify-between">
          <button 
            disabled={page === 1}
            onClick={() => setPage(p => p - 1)}
            className="px-4 py-2 text-sm font-medium text-slate-300 disabled:opacity-50 hover:text-white transition-colors"
          >
            Previous
          </button>
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <span>Page</span>
            <input 
              type="number" 
              min="1" 
              max={Math.max(1, Math.ceil(total / 20))}
              defaultValue={page}
              key={page}
              onBlur={(e) => {
                let p = parseInt(e.target.value);
                if (!isNaN(p)) {
                  p = Math.max(1, Math.min(p, Math.ceil(total / 20)));
                  setPage(p);
                  e.target.value = p;
                } else {
                  e.target.value = page;
                }
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.target.blur();
                }
              }}
              className="bg-slate-900 border border-slate-700 text-white rounded px-2 py-1 w-16 text-center focus:outline-none focus:border-neon-blue"
            />
            <span>of {Math.max(1, Math.ceil(total / 20))}</span>
          </div>
          <button 
            disabled={page * 20 >= total}
            onClick={() => setPage(p => p + 1)}
            className="px-4 py-2 text-sm font-medium text-slate-300 disabled:opacity-50 hover:text-white transition-colors"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
