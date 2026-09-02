import { useState, useEffect, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, AlertTriangle } from 'lucide-react';

export default function PairDetail() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchPair = async () => {
      try {
        const res = await fetch(`/analysis/pairs/${id}`);
        if (res.ok) {
          const json = await res.json();
          setData(json);
        }
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchPair();
  }, [id]);

  // Helper to safely highlight overlapping substrings
  const highlightText = (text, substrings) => {
    if (!substrings || substrings.length === 0 || !text) return text;
    
    const highlightMask = new Array(text.length).fill(false);
    
    // Create a mask of which characters should be highlighted
    substrings.forEach((sub) => {
      let startIndex = 0;
      while ((startIndex = text.indexOf(sub, startIndex)) !== -1) {
        for (let i = 0; i < sub.length; i++) {
          highlightMask[startIndex + i] = true;
        }
        startIndex += sub.length; // Don't allow same substring to overlap itself, but allow different ones
      }
    });

    const chunks = [];
    let isHighlighted = highlightMask[0];
    let currentChunk = text[0];

    for (let i = 1; i < text.length; i++) {
      if (highlightMask[i] === isHighlighted) {
        currentChunk += text[i];
      } else {
        chunks.push({ text: currentChunk, highlighted: isHighlighted });
        isHighlighted = highlightMask[i];
        currentChunk = text[i];
      }
    }
    if (currentChunk) {
      chunks.push({ text: currentChunk, highlighted: isHighlighted });
    }

    return chunks.map((chunk, i) => 
      chunk.highlighted ? (
        <mark key={i} className="bg-neon-purple/40 text-white rounded-xs px-px">{chunk.text}</mark>
      ) : (
        <span key={i}>{chunk.text}</span>
      )
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 rounded-full border-2 border-neon-blue border-t-transparent animate-spin"></div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center py-12">
        <h2 className="text-2xl text-white font-bold mb-4">Pair not found</h2>
        <Link to="/pairs" className="text-neon-blue hover:underline">Back to results</Link>
      </div>
    );
  }

  const { pair, content_a, content_b, shared_shingles } = data;

  return (
    <div className="space-y-6 animate-slide-up">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link to="/pairs" className="p-2 glass-button text-slate-400 hover:text-white">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-3">
              Comparison Detail
              {pair.is_flagged && (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-red-500/20 text-red-400 border border-red-500/30">
                  <AlertTriangle className="w-4 h-4" />
                  Flagged Duplicate
                </span>
              )}
            </h1>
            <p className="text-slate-400 text-sm mt-1">
              Exact Jaccard Similarity: <span className="text-white font-bold">{(pair.exact_similarity * 100).toFixed(2)}%</span>
              <span className="mx-2 text-slate-600">|</span>
              Estimated LSH: <span className="text-white font-bold">{(pair.estimated_similarity * 100).toFixed(2)}%</span>
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Document A */}
        <div className="glass-panel flex flex-col overflow-hidden">
          <div className="bg-slate-900/50 p-4 border-b border-slate-700/50 flex justify-between items-center">
            <h3 className="font-semibold text-slate-200 truncate">{pair.document_a_filename || `Document ${pair.document_a_id}`}</h3>
            <span className="text-xs text-slate-500 bg-slate-800 px-2 py-1 rounded">Source A</span>
          </div>
          <div className="p-6 overflow-y-auto max-h-150 whitespace-pre-wrap font-mono text-sm text-slate-300 leading-relaxed">
            {highlightText(content_a, shared_shingles)}
          </div>
        </div>

        {/* Document B */}
        <div className="glass-panel flex flex-col overflow-hidden">
          <div className="bg-slate-900/50 p-4 border-b border-slate-700/50 flex justify-between items-center">
            <h3 className="font-semibold text-slate-200 truncate">{pair.document_b_filename || `Document ${pair.document_b_id}`}</h3>
            <span className="text-xs text-slate-500 bg-slate-800 px-2 py-1 rounded">Source B</span>
          </div>
          <div className="p-6 overflow-y-auto max-h-150 whitespace-pre-wrap font-mono text-sm text-slate-300 leading-relaxed">
            {highlightText(content_b, shared_shingles)}
          </div>
        </div>
      </div>

      <div className="glass-panel p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Shared Shingles ({shared_shingles.length})</h3>
        <div className="flex flex-wrap gap-2 max-h-48 overflow-y-auto pr-2">
          {shared_shingles.map((shingle, idx) => (
            <span key={idx} className="bg-slate-800/80 border border-slate-700 text-slate-300 px-3 py-1.5 rounded-lg text-xs font-mono break-all hover:bg-neon-purple/20 transition-colors">
              {shingle}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
