"use client";

import { StylePreset } from "@/lib/api";

interface Props {
  preset: StylePreset;
  selected: boolean;
  onClick: () => void;
}

/**
 * Bold Signal — 信息图表风：深色底 + 大数字 + 几何色块 + 数据可视化
 * 设计隐喻：TED 演讲、数据驱动的年报
 */
function BoldSignalPreview({ colors }: { colors: Record<string, string> }) {
  const bg = colors.bg_primary || "#1a1a1a";
  const accent = colors.accent || "#FF5722";
  return (
    <div className="w-full aspect-video relative overflow-hidden" style={{ background: bg }}>
      {/* 大号装饰数字 */}
      <div className="absolute -right-2 -top-3 text-[48px] font-black leading-none" style={{ color: accent, opacity: 0.08 }}>
        2025
      </div>
      {/* 左上角色块 */}
      <div className="absolute top-0 left-0 w-1 h-full" style={{ background: accent }} />
      <div className="absolute inset-0 p-3 pl-4 flex flex-col">
        <div className="text-[7px] tracking-[0.15em] text-white/40 mb-[2px]">年度报告</div>
        <div className="text-[14px] font-black text-white leading-tight" style={{ fontFamily: '"Archivo Black", sans-serif' }}>
          年度战略<br/>规划
        </div>
        {/* 底部数据区 */}
        <div className="mt-auto flex items-end gap-[2px]">
          <div className="flex flex-col items-center flex-1">
            <div className="text-[10px] font-bold" style={{ color: accent }}>↑42%</div>
            <div className="w-full h-6 rounded-sm" style={{ background: accent }} />
          </div>
          {[18, 14, 22, 12].map((h, i) => (
            <div key={i} className="flex-1 rounded-sm" style={{ height: h, background: 'rgba(255,255,255,0.1)' }} />
          ))}
        </div>
      </div>
    </div>
  );
}

/**
 * Electric Studio — 科技创业风：渐变网格 + 非对称布局 + 圆角卡片
 * 设计隐喻：Product Hunt 首页、Y Combinator demo day
 */
function ElectricStudioPreview({ colors }: { colors: Record<string, string> }) {
  const accent = colors.accent || "#4361ee";
  return (
    <div className="w-full aspect-video relative overflow-hidden" style={{ background: `linear-gradient(135deg, #0a0a1a 0%, #1a1a3a 100%)` }}>
      {/* 渐变光晕 */}
      <div className="absolute -top-6 -right-6 w-20 h-20 rounded-full blur-xl animate-on-hover-glow" style={{ background: accent, opacity: 0.2 }} />
      <div className="absolute -bottom-4 -left-4 w-14 h-14 rounded-full blur-lg animate-on-hover-glow" style={{ background: '#7c3aed', opacity: 0.15 }} />
      {/* 内容 */}
      <div className="relative z-10 h-full p-3 flex flex-col">
        <div className="flex items-center gap-1 mb-2">
          <div className="w-2 h-2 rounded-full" style={{ background: accent }} />
          <div className="text-[7px] text-white/50 tracking-wider">产品发布</div>
        </div>
        <div className="text-white text-[12px] font-bold leading-tight" style={{ fontFamily: '"Manrope", sans-serif' }}>
          下一代 AI<br/>产品体验
        </div>

        {/* 功能卡片 */}
        <div className="mt-auto flex gap-1">
          {["智能", "高效", "安全"].map((label, i) => (
            <div key={i} className="flex-1 rounded-md p-[4px] text-center" style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)' }}>
              <div className="text-[7px] text-white/70">{label}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/**
 * Dark Botanical — 奢侈杂志风：有机形状 + 衬线字体 + 金色线条 + 层叠纹理
 * 设计隐喻：Vogue、奢侈品发布会
 */
function DarkBotanicalPreview({ colors }: { colors: Record<string, string> }) {
  const warm = colors.accent_warm || "#d4a574";
  const pink = colors.accent_pink || "#e8b4b8";
  return (
    <div className="w-full aspect-video relative overflow-hidden" style={{ background: "#0c0c0a" }}>
      {/* 有机曲线装饰 */}
      <svg className="absolute inset-0 w-full h-full" viewBox="0 0 160 100" preserveAspectRatio="none">
        <path d="M0 80 Q40 60 80 75 T160 65" stroke={warm} fill="none" strokeWidth="0.3" opacity="0.4" />
        <path d="M0 30 Q50 50 100 35 T160 40" stroke={pink} fill="none" strokeWidth="0.3" opacity="0.3" />
        <circle cx="130" cy="20" r="12" fill="none" stroke={warm} strokeWidth="0.3" opacity="0.2" />
      </svg>
      {/* 居中内容 */}
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center px-4">
        <div className="text-[6px] tracking-[0.3em] mb-2" style={{ color: warm }}>臻选系列</div>
        <div className="text-[14px] leading-tight" style={{ fontFamily: '"Cormorant Garamond", serif', color: '#ede8e2' }}>
          优雅源于
        </div>
        <div className="text-[14px] leading-tight italic" style={{ fontFamily: '"Cormorant Garamond", serif', color: pink }}>
          &nbsp;克制
        </div>
        <div className="flex items-center gap-2 mt-2">
          <div className="w-6 h-[0.5px]" style={{ background: warm }} />
          <div className="w-1.5 h-1.5 rotate-45 border" style={{ borderColor: warm }} />
          <div className="w-6 h-[0.5px]" style={{ background: warm }} />
        </div>
      </div>
    </div>
  );
}

/**
 * Notebook Tabs — 手账教育风：彩色标签 + 手绘线条感 + 纸质纹理 + 便利贴
 * 设计隐喻：Notion、课堂笔记、文具
 */
function NotebookTabsPreview({ colors }: { colors: Record<string, string> }) {
  const tabs = ["#98d4bb", "#c7b8ea", "#f4b8c5", "#ffd89b"];
  const pageBg = colors.bg_page || "#f8f6f1";
  return (
    <div className="w-full aspect-video flex flex-col" style={{ background: "#3d3d3d" }}>
      {/* 彩色标签 */}
      <div className="flex gap-[1px] px-2 pt-2">
        {tabs.map((c, i) => (
          <div
            key={i}
            className="px-[6px] py-[3px] rounded-t text-[7px] font-bold transition-all"
            style={{
              background: i === 0 ? c : `${c}55`,
              color: '#333',
              transform: i === 0 ? 'translateY(-1px)' : 'none',
              boxShadow: i === 0 ? '0 -1px 3px rgba(0,0,0,0.1)' : 'none',
            }}
          >
            {["概述", "数据", "方案", "总结"][i]}
          </div>
        ))}
      </div>
      {/* 笔记本页面 */}
      <div className="flex-1 mx-2 mb-2 rounded-b p-2 relative" style={{ background: pageBg }}>
        {/* 横线 */}
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="absolute w-full h-[0.5px] left-0" style={{ top: `${25 + i * 22}%`, background: '#e0ddd5' }} />
        ))}
        {/* 内容 */}
        <div className="relative z-10">
          <div className="text-[10px] font-bold text-gray-800" style={{ fontFamily: '"Bodoni Moda", serif' }}>项目概述</div>
          <div className="mt-2 flex gap-2">
            {/* 便利贴 */}
            <div className="w-10 h-8 rounded-sm p-[2px] shadow-sm rotate-[-2deg]" style={{ background: tabs[3] }}>
              <div className="text-[5px] text-gray-700 font-medium">重点!</div>
            </div>
            <div className="w-10 h-8 rounded-sm p-[2px] shadow-sm rotate-[1deg]" style={{ background: tabs[2] }}>
              <div className="text-[5px] text-gray-700 font-medium">待办</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Corporate Navy — 咨询公司风：精密网格 + 仪表盘 + 指标矩阵 + 蓝色主调
 * 设计隐喻：McKinsey 报告、Bloomberg 终端
 */
function CorporateNavyPreview({ colors }: { colors: Record<string, string> }) {
  const blue = colors.accent_blue || "#0052d9";
  const green = colors.accent_green || "#059669";
  return (
    <div className="w-full aspect-video flex flex-col" style={{ background: "#f0f2f5" }}>
      {/* 顶部深色导航 */}
      <div className="h-[14px] px-2 flex items-center justify-between" style={{ background: '#1e293b' }}>
        <div className="flex gap-[3px] items-center">
          <div className="w-[4px] h-[4px] rounded-full" style={{ background: blue }} />
          <div className="text-[5px] text-white/80 font-medium">数据看板</div>
        </div>
        <div className="text-[5px] text-white/40">2025年第四季度</div>
      </div>
      {/* 指标网格 */}
      <div className="flex-1 p-[6px] grid grid-cols-3 grid-rows-2 gap-[4px]">
        {[
          { val: "85%", label: "达成率", color: blue, bar: 85 },
          { val: "+24%", label: "同比增长", color: green, bar: 60 },
          { val: "¥3.2M", label: "营收", color: "#6366f1", bar: 72 },
          { val: "4.8", label: "NPS", color: "#f59e0b", bar: 96 },
          { val: "12ms", label: "延迟 P99", color: green, bar: 40 },
          { val: "99.9%", label: "可用性", color: blue, bar: 99 },
        ].map((item, i) => (
          <div key={i} className="bg-white rounded border border-gray-200/80 p-[3px] flex flex-col justify-center items-center">
            <div className="text-[8px] font-black leading-none" style={{ color: item.color }}>{item.val}</div>
            <div className="text-[5px] text-gray-400 mt-[1px]">{item.label}</div>
            <div className="w-full h-[2px] mt-[2px] bg-gray-100 rounded-full overflow-hidden">
              <div className="h-full rounded-full" style={{ width: `${item.bar}%`, background: item.color }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Neon Cyber — 赛博朋克风：扫描线 + 霓虹发光 + 等宽字体 + 终端感
 * 设计隐喻：黑客帝国、Cyberpunk 2077、终端界面
 */
function NeonCyberPreview({ colors }: { colors: Record<string, string> }) {
  const cyan = colors.accent_cyan || "#00f5ff";
  const magenta = colors.accent_magenta || "#ff00e5";
  return (
    <div className="w-full aspect-video relative overflow-hidden" style={{ background: "#0a0014" }}>
      {/* 扫描线 */}
      <div className="absolute inset-0" style={{
        backgroundImage: `repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0,245,255,0.03) 3px, rgba(0,245,255,0.03) 4px)`,
      }} />
      {/* Hover扫描效果 */}
      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 animate-on-hover-scan" style={{ background: `linear-gradient(180deg, transparent 40%, rgba(0,245,255,0.06) 50%, transparent 60%)` }} />
      {/* 边角装饰 */}
      <div className="absolute top-1 left-1 w-3 h-3 border-t border-l" style={{ borderColor: cyan }} />
      <div className="absolute bottom-1 right-1 w-3 h-3 border-b border-r" style={{ borderColor: magenta }} />
      {/* 内容 */}
      <div className="relative z-10 h-full p-3 flex flex-col">
        <div className="text-[6px] font-mono" style={{ color: cyan, opacity: 0.6 }}>{'>'} 系统就绪_</div>
        <div className="mt-1 text-[13px] font-black tracking-wider" style={{ fontFamily: '"Orbitron", sans-serif', color: '#e0e0ff', textShadow: `0 0 8px ${cyan}44` }}>
          未来已来
        </div>
        <div className="text-[8px] font-mono mt-[2px]" style={{ color: magenta }}>
          ██████░░░░ 60%
        </div>
        {/* 底部数据行 */}
        <div className="mt-auto flex justify-between text-[6px] font-mono" style={{ color: cyan, opacity: 0.7 }}>
          <span>延迟:3ms</span>
          <span>节点:128</span>
          <span>状态:在线</span>
        </div>
      </div>
    </div>
  );
}

/**
 * Pastel Geometry — 柔和几何风：圆形三角 + 糖果色渐变 + 圆角一切 + 活力友好
 * 设计隐喻：Dribbble、儿童教育、创意工作坊
 */
function PastelGeometryPreview({ colors }: { colors: Record<string, string> }) {
  const coral = colors.accent_coral || "#ff7f7f";
  const mint = colors.accent_mint || "#7fdfbf";
  const lavender = colors.accent_lavender || "#b8a9f0";
  return (
    <div className="w-full aspect-video relative overflow-hidden" style={{ background: "#fef9f4" }}>
      {/* 几何装饰 */}
      <div className="absolute top-2 right-3 w-8 h-8 rounded-full opacity-30" style={{ background: coral }} />
      <div className="absolute bottom-3 left-2 w-5 h-5 rotate-45 rounded-sm opacity-25" style={{ background: lavender }} />
      <div className="absolute top-6 left-8 w-0 h-0 opacity-20" style={{ borderLeft: '6px solid transparent', borderRight: '6px solid transparent', borderBottom: `10px solid ${mint}` }} />
      {/* 内容 */}
      <div className="relative z-10 h-full p-3 flex flex-col">
        <div className="text-[12px] font-bold text-gray-800" style={{ fontFamily: '"Quicksand", sans-serif' }}>
          创意工坊
        </div>
        <div className="text-[7px] text-gray-500 mt-[2px]">激发灵感的旅程</div>
        {/* 功能卡片 */}
        <div className="mt-auto flex gap-[4px]">
          {[
            { label: "探索", bg: coral },
            { label: "构思", bg: mint },
            { label: "创造", bg: lavender },
          ].map((item, i) => (
            <div key={i} className="flex-1 rounded-lg p-[4px] text-center" style={{ background: `${item.bg}33` }}>
              <div className="w-3 h-3 rounded-full mx-auto mb-[2px]" style={{ background: `${item.bg}66` }} />
              <div className="text-[6px] font-bold text-gray-700">{item.label}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/**
 * Vintage Editorial — 复古报刊风：分栏排版 + 装饰线 + 首字下沉 + 报纸版式
 * 设计隐喻：纽约时报、经济学人、老式杂志
 */
function VintageEditorialPreview({ colors }: { colors: Record<string, string> }) {
  const red = colors.accent_red || "#c0392b";
  const gold = colors.accent_gold || "#b8860b";
  return (
    <div className="w-full aspect-video relative overflow-hidden" style={{ background: "#f5f0e8" }}>
      {/* 顶部装饰线 */}
      <div className="absolute top-0 left-0 w-full h-[3px]" style={{ background: red }} />
      <div className="absolute top-[4px] left-0 w-full h-[0.5px] bg-gray-800" />
      {/* 内容 */}
      <div className="relative h-full p-2 pt-3 flex flex-col">
        {/* 报头 */}
        <div className="text-center border-b border-gray-800 pb-1 mb-1">
          <div className="text-[11px] font-black tracking-tight" style={{ fontFamily: '"Playfair Display", serif', color: '#1a1a1a' }}>
            深度洞察
          </div>
          <div className="text-[5px] text-gray-500 mt-[1px]">第四期 · 二〇二五年春</div>
        </div>
        {/* 双栏 */}
        <div className="flex-1 flex gap-[4px]">
          <div className="flex-1 flex flex-col">
            <span className="text-[14px] font-black float-left leading-none mr-[2px]" style={{ color: red, fontFamily: '"Playfair Display", serif' }}>趋</span>
            <div className="space-y-[2px]">
              {[100, 90, 100, 80, 95].map((w, i) => (
                <div key={i} className="h-[2px] rounded-full" style={{ width: `${w}%`, background: '#1a1a1a', opacity: 0.15 + i * 0.03 }} />
              ))}
            </div>
          </div>
          <div className="w-[0.5px] bg-gray-300" />
          <div className="flex-1 space-y-[2px] pt-1">
            {[85, 100, 75, 95, 88].map((w, i) => (
              <div key={i} className="h-[2px] rounded-full" style={{ width: `${w}%`, background: '#1a1a1a', opacity: 0.12 + i * 0.03 }} />
            ))}
          </div>
        </div>
        {/* 底部页码 */}
        <div className="text-center text-[5px] mt-1 pt-[2px] border-t border-gray-300" style={{ color: gold }}>
          — 1 —
        </div>
      </div>
    </div>
  );
}

/**
 * Sketch Whiteboard — 手绘白板风：手写体 + 涂鸦箭头 + 便签 + 白板感
 * 设计隐喻：Miro、头脑风暴、设计思维工作坊
 */
function SketchWhiteboardPreview({ colors }: { colors: Record<string, string> }) {
  const blue = colors.accent_blue || "#4a90d9";
  const red = colors.accent_red || "#e74c3c";
  const yellow = colors.accent_yellow || "#f1c40f";
  return (
    <div className="w-full aspect-video relative overflow-hidden" style={{ background: "#ffffff" }}>
      {/* 网格点 */}
      <div className="absolute inset-0" style={{
        backgroundImage: `radial-gradient(circle, #ddd 0.8px, transparent 0.8px)`,
        backgroundSize: '10px 10px'
      }} />
      {/* 手绘内容 */}
      <div className="relative z-10 h-full p-3 flex flex-col">
        <div className="text-[12px] font-bold" style={{ fontFamily: '"Caveat", cursive', color: '#333' }}>
          头脑风暴 💡
        </div>
        {/* 手绘箭头 SVG */}
        <svg className="absolute top-5 right-6 w-8 h-6" viewBox="0 0 40 30">
          <path d="M5 25 Q20 5 35 15" stroke={red} fill="none" strokeWidth="1.5" strokeLinecap="round" strokeDasharray="2 2" />
          <path d="M30 12 L35 15 L30 18" stroke={red} fill="none" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
        {/* 便签卡片 */}
        <div className="mt-auto flex gap-2">
          <div className="flex-1 p-[4px] rounded-sm shadow-sm rotate-[-1deg]" style={{ background: yellow, border: '1px solid #e0b800' }}>
            <div className="text-[6px] font-bold text-gray-800" style={{ fontFamily: '"Patrick Hand", cursive' }}>想法 A</div>
            <div className="text-[5px] text-gray-600 mt-[1px]">用户调研</div>
          </div>
          <div className="flex-1 p-[4px] rounded-sm shadow-sm rotate-[2deg]" style={{ background: '#e8f4fd', border: `1px solid ${blue}44` }}>
            <div className="text-[6px] font-bold text-gray-800" style={{ fontFamily: '"Patrick Hand", cursive' }}>想法 B</div>
            <div className="text-[5px] text-gray-600 mt-[1px]">原型设计</div>
          </div>
          <div className="flex-1 p-[4px] rounded-sm shadow-sm rotate-[-0.5deg]" style={{ background: '#fde8e8', border: `1px solid ${red}44` }}>
            <div className="text-[6px] font-bold text-gray-800" style={{ fontFamily: '"Patrick Hand", cursive' }}>想法 C</div>
            <div className="text-[5px] text-gray-600 mt-[1px]">快速验证</div>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Isometric Tech — 等距科幻风：等距网格 + 3D几何 + 蓝图感 + 工程结构
 * 设计隐喻：技术架构图、3D城市、工程蓝图
 */
function IsometricTechPreview({ colors }: { colors: Record<string, string> }) {
  const teal = colors.accent_teal || "#00d4aa";
  const orange = colors.accent_orange || "#ff6b35";
  return (
    <div className="w-full aspect-video relative overflow-hidden" style={{ background: "#1a1a2e" }}>
      {/* 等距网格 */}
      <svg className="absolute inset-0 w-full h-full opacity-20" viewBox="0 0 160 100">
        {[0, 20, 40, 60, 80, 100, 120, 140, 160].map((x, i) => (
          <line key={`v${i}`} x1={x} y1="0" x2={x} y2="100" stroke="#2a2a4a" strokeWidth="0.5" />
        ))}
        {[0, 20, 40, 60, 80, 100].map((y, i) => (
          <line key={`h${i}`} x1="0" y1={y} x2="160" y2={y} stroke="#2a2a4a" strokeWidth="0.5" />
        ))}
      </svg>
      {/* 3D 等距方块 */}
      <svg className="absolute bottom-2 left-3 w-16 h-14 animate-on-hover-float" viewBox="0 0 60 50">
        <polygon points="30,5 55,18 55,38 30,50 5,38 5,18" fill="none" stroke={teal} strokeWidth="0.8" opacity="0.6" />
        <polygon points="30,5 55,18 30,30 5,18" fill={`${teal}15`} stroke={teal} strokeWidth="0.5" />
        <polygon points="30,30 55,18 55,38 30,50" fill={`${teal}0a`} stroke={teal} strokeWidth="0.5" />
        <polygon points="30,30 5,18 5,38 30,50" fill={`${teal}08`} stroke={teal} strokeWidth="0.5" />
      </svg>
      {/* 内容 */}
      <div className="relative z-10 h-full p-3 flex flex-col">
        <div className="text-[11px] font-bold tracking-wide" style={{ fontFamily: '"Rajdhani", sans-serif', color: '#e0e0e0' }}>
          系统架构
        </div>
        <div className="text-[7px] mt-[2px]" style={{ color: teal }}>v3.0 技术蓝图</div>
        {/* 指标 */}
        <div className="mt-auto flex gap-2">
          <div className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-sm" style={{ background: teal }} />
            <span className="text-[6px]" style={{ color: '#e0e0e0' }}>核心层</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-sm" style={{ background: orange }} />
            <span className="text-[6px]" style={{ color: '#e0e0e0' }}>接入层</span>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Split Contrast — 撞色分割风：黑白对半 + 文字跨越 + 戏剧张力
 * 设计隐喻：时装秀、先锋艺术展、Supreme
 */
function SplitContrastPreview({ colors }: { colors: Record<string, string> }) {
  const accent = colors.accent || "#ff3366";
  return (
    <div className="w-full aspect-video relative overflow-hidden">
      {/* 左黑右白对角分割 */}
      <div className="absolute inset-0" style={{ background: '#000' }} />
      <div className="absolute inset-0" style={{ clipPath: 'polygon(45% 0, 100% 0, 100% 100%, 55% 100%)', background: '#fff' }} />
      {/* 跨越分界线的文字 */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="text-[18px] font-black tracking-tighter" style={{ fontFamily: '"Bebas Neue", sans-serif', background: `linear-gradient(90deg, #fff 45%, #000 45%)`, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          对比
        </div>
      </div>
      {/* 强调色点 */}
      <div className="absolute bottom-3 left-1/2 -translate-x-1/2 w-6 h-1 rounded-full" style={{ background: accent }} />
      <div className="absolute top-2 right-3 text-[6px] font-bold" style={{ color: accent }}>前卫</div>
    </div>
  );
}

/**
 * Clay 3D — 3D黏土风：柔和阴影 + Blob形状 + 圆润一切 + 品牌质感
 * 设计隐喻：Notion AI、Linear、现代SaaS landing
 */
function Clay3DPreview({ colors }: { colors: Record<string, string> }) {
  const purple = colors.accent_purple || "#7c3aed";
  const orange = colors.accent_orange || "#fb923c";
  const pink = colors.accent_pink || "#f472b6";
  return (
    <div className="w-full aspect-video relative overflow-hidden" style={{ background: 'linear-gradient(135deg, #f0e6ff 0%, #fdf2f8 100%)' }}>
      {/* Blob 装饰 */}
      <div className="absolute top-2 right-4 w-10 h-8 rounded-[40%_60%_60%_40%/60%_40%_60%_40%]" style={{ background: `${purple}22`, boxShadow: `4px 4px 0 ${purple}33` }} />
      <div className="absolute bottom-4 left-3 w-6 h-6 rounded-[50%_50%_40%_60%/40%_60%_50%_50%]" style={{ background: `${orange}22`, boxShadow: `3px 3px 0 ${orange}33` }} />
      {/* 内容 */}
      <div className="relative z-10 h-full p-3 flex flex-col">
        <div className="text-[12px] font-bold" style={{ fontFamily: '"Fredoka", sans-serif', color: '#2d1b4e' }}>
          品牌升级
        </div>
        <div className="text-[7px] mt-[2px]" style={{ color: '#6b5b8a' }}>打造有温度的体验</div>
        {/* 3D 按钮卡片 */}
        <div className="mt-auto flex gap-2">
          {[
            { label: "设计", color: purple },
            { label: "开发", color: orange },
            { label: "发布", color: pink },
          ].map((item, i) => (
            <div key={i} className="flex-1 rounded-xl p-[5px] text-center text-[6px] font-bold text-white" style={{ background: item.color, boxShadow: `0 3px 0 ${item.color}88, 0 4px 8px ${item.color}33` }}>
              {item.label}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/**
 * Terminal Hacker — 终端黑客风：终端窗口 + 命令行 + 语法高亮 + 代码美学
 * 设计隐喻：VS Code、GitHub Dark、黑客电影
 */
function TerminalHackerPreview({ colors }: { colors: Record<string, string> }) {
  const green = colors.accent_green || "#39d353";
  const yellow = colors.accent_yellow || "#e3b341";
  const red = colors.accent_red || "#f85149";
  return (
    <div className="w-full aspect-video relative overflow-hidden" style={{ background: "#0d1117" }}>
      {/* 终端标题栏 */}
      <div className="h-[12px] px-2 flex items-center gap-[3px]" style={{ background: '#161b22', borderBottom: '1px solid #30363d' }}>
        <div className="w-[5px] h-[5px] rounded-full" style={{ background: red }} />
        <div className="w-[5px] h-[5px] rounded-full" style={{ background: yellow }} />
        <div className="w-[5px] h-[5px] rounded-full" style={{ background: green }} />
        <div className="text-[5px] text-gray-500 ml-2 font-mono">~/presentation</div>
      </div>
      {/* 终端内容 */}
      <div className="p-2 font-mono text-[6px] leading-relaxed">
        <div><span style={{ color: green }}>$</span> <span style={{ color: '#c9d1d9' }}>cat 主题.md</span></div>
        <div className="mt-[2px]"><span style={{ color: '#8b949e' }}># 技术分享</span></div>
        <div><span style={{ color: yellow }}>## </span><span style={{ color: '#c9d1d9' }}>架构设计原则</span></div>
        <div className="mt-[2px]"><span style={{ color: green }}>+</span> 高可用</div>
        <div><span style={{ color: green }}>+</span> 可扩展</div>
        <div><span style={{ color: red }}>-</span> <span className="line-through opacity-50">单点故障</span></div>
        <div className="mt-[2px]"><span style={{ color: green }}>$</span> <span className="animate-pulse">▊</span></div>
      </div>
    </div>
  );
}

/**
 * Watercolor Art — 水彩画风：晕染边缘 + 流动色块 + 手工纸质感
 * 设计隐喻：画展、诗集、手工绘本
 */
function WatercolorArtPreview({ colors }: { colors: Record<string, string> }) {
  const blue = colors.wash_blue || "#74b9ff";
  const pink = colors.wash_pink || "#fd79a8";
  const green = colors.wash_green || "#55efc4";
  return (
    <div className="w-full aspect-video relative overflow-hidden" style={{ background: "#fdfcfa" }}>
      {/* 水彩色块 */}
      <div className="absolute top-0 right-0 w-16 h-12 rounded-[50%] blur-[8px] opacity-40" style={{ background: blue }} />
      <div className="absolute bottom-0 left-2 w-14 h-10 rounded-[60%_40%_50%_50%] blur-[6px] opacity-35" style={{ background: pink }} />
      <div className="absolute top-6 left-10 w-8 h-8 rounded-[50%] blur-[5px] opacity-25" style={{ background: green }} />
      {/* 内容 */}
      <div className="relative z-10 h-full p-3 flex flex-col justify-end">
        <div className="text-[11px] font-medium" style={{ fontFamily: '"Libre Baskerville", serif', color: '#2c3e50' }}>
          时光的颜色
        </div>
        <div className="text-[7px] mt-[2px] italic" style={{ color: '#636e72' }}>每一笔都是故事</div>
        <div className="flex gap-1 mt-2">
          {[blue, pink, green].map((c, i) => (
            <div key={i} className="w-4 h-2 rounded-full opacity-60" style={{ background: c }} />
          ))}
        </div>
      </div>
    </div>
  );
}

/**
 * Swiss Modern — 瑞士现代主义：严格网格 + 无衬线 + 红色唯一强调 + 数学精确
 * 设计隐喻：包豪斯、国际主义平面设计、Dieter Rams
 */
function SwissModernPreview({ colors }: { colors: Record<string, string> }) {
  const red = colors.accent_red || "#ff0000";
  return (
    <div className="w-full aspect-video relative overflow-hidden" style={{ background: "#ffffff" }}>
      {/* 网格线 */}
      <div className="absolute inset-0" style={{
        backgroundImage: `linear-gradient(#e5e5e5 1px, transparent 1px), linear-gradient(90deg, #e5e5e5 1px, transparent 1px)`,
        backgroundSize: '20px 20px'
      }} />
      {/* 内容——严格对齐 */}
      <div className="relative z-10 h-full p-3 flex flex-col">
        <div className="text-[14px] font-bold leading-none tracking-tight" style={{ fontFamily: '"Inter", sans-serif', color: '#000' }}>
          秩序
        </div>
        <div className="text-[7px] text-gray-500 mt-1 tracking-wide">即是美</div>
        {/* 红色色块 */}
        <div className="mt-auto flex items-end gap-[3px]">
          <div className="w-4 h-8" style={{ background: red }} />
          <div className="w-4 h-5 bg-black" />
          <div className="w-4 h-3 bg-gray-300" />
          <div className="flex-1" />
          <div className="text-[6px] text-gray-400 self-end">Grid 12px</div>
        </div>
      </div>
    </div>
  );
}

/**
 * Dark Gold Luxury — 暗金奢华风：纯黑底 + 金色装饰线 + 衬线大字 + 仪式感
 * 设计隐喻：奥斯卡颁奖、奢侈品年会、高端晚宴
 */
function DarkGoldLuxuryPreview({ colors }: { colors: Record<string, string> }) {
  const gold = colors.gold || "#d4af37";
  const goldLight = colors.gold_light || "#f4e4a6";
  return (
    <div className="w-full aspect-video relative overflow-hidden" style={{ background: "#0a0a0a" }}>
      {/* 金色边框装饰 */}
      <div className="absolute inset-2 border rounded-sm" style={{ borderColor: `${gold}33` }} />
      <div className="absolute inset-[10px] border rounded-sm" style={{ borderColor: `${gold}18` }} />
      {/* 角落装饰 */}
      <svg className="absolute top-2 left-2 w-4 h-4" viewBox="0 0 20 20">
        <path d="M0 15 L0 0 L15 0" fill="none" stroke={gold} strokeWidth="1" />
      </svg>
      <svg className="absolute bottom-2 right-2 w-4 h-4" viewBox="0 0 20 20">
        <path d="M5 20 L20 20 L20 5" fill="none" stroke={gold} strokeWidth="1" />
      </svg>
      {/* 中心内容 */}
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        <div className="text-[5px] tracking-[0.4em]" style={{ color: gold }}>年度盛典</div>
        <div className="text-[14px] font-bold mt-1" style={{ fontFamily: '"Cinzel", serif', color: goldLight }}>
          荣耀时刻
        </div>
        <div className="w-12 h-[0.5px] mt-2" style={{ background: `linear-gradient(90deg, transparent, ${gold}, transparent)` }} />
        <div className="text-[6px] mt-1" style={{ color: `${gold}99` }}>2025 · 颁奖典礼</div>
      </div>
    </div>
  );
}

/**
 * Zen Minimal — 禅意极简风：大量留白 + 单焦点 + 水墨质感 + 东方美学
 * 设计隐喻：无印良品、枯山水、书法
 */
function ZenMinimalPreview({ colors }: { colors: Record<string, string> }) {
  const ink = colors.accent_ink || "#1a1a1a";
  const bamboo = colors.accent_bamboo || "#6b8e6b";
  return (
    <div className="w-full aspect-video relative" style={{ background: "#fafaf8" }}>
      {/* 水墨圆 */}
      <div className="absolute top-4 right-6 w-10 h-10 rounded-full opacity-[0.04]" style={{ background: ink }} />
      {/* 极简内容——巨量留白 */}
      <div className="absolute inset-0 flex flex-col items-start justify-end p-4">
        <div className="text-[13px] font-light tracking-wide" style={{ fontFamily: '"Noto Serif SC", serif', color: ink }}>
          静
        </div>
        <div className="w-8 h-[0.5px] mt-1 mb-1" style={{ background: ink, opacity: 0.3 }} />
        <div className="text-[7px]" style={{ color: '#9ca3af' }}>以简驭繁</div>
      </div>
      {/* 右下竹色小点 */}
      <div className="absolute bottom-3 right-4 w-1 h-1 rounded-full" style={{ background: bamboo }} />
    </div>
  );
}

/**
 * Gradient Aurora — 极光渐变风：全屏渐变 + 玻璃拟态 + 流体色彩
 * 设计隐喻：Apple 发布会、Spotify Wrapped、3D 艺术
 */
function GradientAuroraPreview({ colors }: { colors: Record<string, string> }) {
  const g1 = colors.gradient_1 || "#667eea";
  const g2 = colors.gradient_2 || "#764ba2";
  const g3 = colors.gradient_3 || "#f093fb";
  return (
    <div className="w-full aspect-video relative overflow-hidden" style={{ background: `linear-gradient(135deg, ${g1} 0%, ${g2} 50%, ${g3} 100%)` }}>
      {/* 光斑 */}
      <div className="absolute top-1 left-4 w-12 h-12 rounded-full blur-lg animate-on-hover-glow" style={{ background: '#4facfe', opacity: 0.3 }} />
      <div className="absolute bottom-2 right-2 w-8 h-8 rounded-full blur-md animate-on-hover-float" style={{ background: g3, opacity: 0.4 }} />
      {/* 玻璃卡片 */}
      <div className="absolute inset-3 rounded-xl flex flex-col items-center justify-center" style={{ background: 'rgba(255,255,255,0.12)', backdropFilter: 'blur(8px)', border: '1px solid rgba(255,255,255,0.2)' }}>
        <div className="text-white text-[12px] font-bold" style={{ fontFamily: '"Outfit", sans-serif' }}>灵感绽放</div>
        <div className="text-white/60 text-[7px] mt-1">沉浸式视觉体验</div>
        <div className="flex gap-1 mt-2">
          {[g1, g2, g3, '#4facfe'].map((c, i) => (
            <div key={i} className="w-2 h-2 rounded-full" style={{ background: c, boxShadow: `0 0 4px ${c}` }} />
          ))}
        </div>
      </div>
    </div>
  );
}

const PREVIEW_MAP: Record<string, React.FC<{ colors: Record<string, string> }>> = {
  "bold-signal": BoldSignalPreview,
  "electric-studio": ElectricStudioPreview,
  "dark-botanical": DarkBotanicalPreview,
  "notebook-tabs": NotebookTabsPreview,
  "corporate-navy": CorporateNavyPreview,
  "neon-cyber": NeonCyberPreview,
  "pastel-geometry": PastelGeometryPreview,
  "vintage-editorial": VintageEditorialPreview,
  "sketch-whiteboard": SketchWhiteboardPreview,
  "isometric-tech": IsometricTechPreview,
  "split-contrast": SplitContrastPreview,
  "clay-3d": Clay3DPreview,
  "terminal-hacker": TerminalHackerPreview,
  "watercolor-art": WatercolorArtPreview,
  "swiss-modern": SwissModernPreview,
  "dark-gold-luxury": DarkGoldLuxuryPreview,
  "zen-minimal": ZenMinimalPreview,
  "gradient-aurora": GradientAuroraPreview,
};

export default function TemplateCard({ preset, selected, onClick }: Props) {
  const PreviewComponent = PREVIEW_MAP[preset.id];

  return (
    <button
      onClick={onClick}
      className={`style-card group relative text-left rounded-xl border-2 transition-all duration-300 hover:scale-[1.03] hover:-translate-y-1 overflow-hidden shadow-sm ${
        selected
          ? "border-blue-500 ring-2 ring-blue-200 shadow-blue-100 scale-[1.01]"
          : "border-gray-200 hover:border-gray-400 hover:shadow-lg"
      }`}
    >
      {PreviewComponent ? (
        <PreviewComponent colors={preset.colors} />
      ) : (
        <div className="w-full aspect-video bg-gray-200" />
      )}

      <div className="px-2.5 py-1.5 bg-white">
        <h3 className="font-medium text-xs text-gray-700 truncate">{preset.name}</h3>
      </div>

      {selected && (
        <span className="absolute top-2 right-2 w-5 h-5 bg-blue-500 rounded-full flex items-center justify-center text-white text-xs font-bold shadow">
          ✓
        </span>
      )}
    </button>
  );
}
