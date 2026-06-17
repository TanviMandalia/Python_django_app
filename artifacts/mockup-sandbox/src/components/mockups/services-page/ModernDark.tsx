import React from "react";
import {
  Activity,
  ArrowRight,
  Brain,
  Calendar,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  Crosshair,
  Dumbbell,
  HeartPulse,
  Home,
  MessageSquare,
  Sparkles,
  Stethoscope,
  Syringe,
  Timer
} from "lucide-react";

export function ModernDark() {
  return (
    <div className="min-h-screen bg-[#111111] text-gray-300 font-sans selection:bg-[#F5C518] selection:text-[#111]">
      <style dangerouslySetInnerHTML={{ __html: `
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');
        
        .font-outfit { font-family: 'Outfit', sans-serif; }
        
        .gold-gradient-text {
          background: linear-gradient(135deg, #F5C518 0%, #D4A017 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }

        .gold-glow {
          box-shadow: 0 0 20px rgba(245, 197, 24, 0.15);
        }

        .gold-glow-hover:hover {
          box-shadow: 0 0 30px rgba(245, 197, 24, 0.25);
          border-color: rgba(245, 197, 24, 0.5);
        }
        
        .bento-card {
          background: #1A1A1A;
          border: 1px solid rgba(255, 255, 255, 0.05);
          transition: all 0.3s ease;
        }
        
        .bg-diagonal {
          background: linear-gradient(135deg, rgba(245,197,24,0.05) 0%, rgba(17,17,17,1) 40%, rgba(17,17,17,1) 100%);
        }
      `}} />

      {/* Hero Section */}
      <section className="relative overflow-hidden py-24 lg:py-32 bg-diagonal">
        <div className="absolute top-0 right-0 -mr-32 -mt-32 w-96 h-96 bg-[#F5C518] rounded-full blur-[120px] opacity-10" />
        <div className="absolute bottom-0 left-0 -ml-32 -mb-32 w-80 h-80 bg-[#F5C518] rounded-full blur-[100px] opacity-5" />
        
        <div className="max-w-7xl mx-auto px-6 relative z-10">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[#1A1A1A] border border-[#F5C518]/20 text-[#F5C518] text-sm font-semibold mb-8 uppercase tracking-wider">
              <Sparkles className="w-4 h-4" />
              <span>Premium Physiotherapy in Jamnagar</span>
            </div>
            <h1 className="text-5xl lg:text-7xl font-extrabold text-white font-outfit leading-[1.1] mb-6">
              Reclaim Your <br />
              <span className="gold-gradient-text">Movement & Life.</span>
            </h1>
            <p className="text-lg lg:text-xl text-gray-400 mb-10 leading-relaxed max-w-2xl">
              Advanced rehabilitation, cutting-edge treatments, and personalized care by Dr. Dhvani Patalia. We don't just treat the pain; we heal the cause.
            </p>
            <div className="flex flex-col sm:flex-row gap-4">
              <button className="px-8 py-4 bg-[#F5C518] text-[#111] font-bold rounded-lg hover:bg-[#D4A017] transition-all flex items-center justify-center gap-2">
                <Calendar className="w-5 h-5" />
                Book Assessment
              </button>
              <button className="px-8 py-4 bg-transparent border border-gray-600 text-white font-bold rounded-lg hover:bg-white/5 transition-all flex items-center justify-center gap-2">
                <MessageSquare className="w-5 h-5" />
                Contact Clinic
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Services Bento Grid */}
      <section className="py-24 relative">
        <div className="max-w-7xl mx-auto px-6">
          <div className="mb-16">
            <h2 className="text-4xl lg:text-5xl font-bold text-white font-outfit mb-4">Specialized <span className="gold-gradient-text">Services</span></h2>
            <p className="text-gray-400 max-w-2xl text-lg">Comprehensive physiotherapy and rehabilitation solutions tailored to your specific needs.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 auto-rows-[minmax(280px,auto)]">
            
            {/* Pain Management - Large Card */}
            <div className="bento-card gold-glow-hover rounded-2xl p-8 lg:col-span-2 flex flex-col justify-between group">
              <div>
                <div className="w-14 h-14 bg-[#111] border border-[#F5C518]/30 rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                  <Activity className="w-7 h-7 text-[#F5C518]" />
                </div>
                <h3 className="text-2xl font-bold text-white font-outfit mb-4">Pain Management</h3>
                <p className="text-gray-400 mb-6">Targeted relief and long-term solutions for chronic and acute pain conditions.</p>
                <div className="flex flex-wrap gap-2">
                  {['Neck Pain', 'Back Pain', 'Slip Disc', 'Sciatica', 'Shoulder Pain', 'Knee & Joint', 'Muscle Spasm'].map(item => (
                    <span key={item} className="px-3 py-1 bg-[#111] border border-gray-800 text-sm rounded-full text-gray-300">{item}</span>
                  ))}
                </div>
              </div>
            </div>

            {/* Frozen Shoulder */}
            <div className="bento-card gold-glow-hover rounded-2xl p-8 flex flex-col justify-between group">
              <div>
                <div className="w-14 h-14 bg-[#111] border border-[#F5C518]/30 rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                  <Crosshair className="w-7 h-7 text-[#F5C518]" />
                </div>
                <h3 className="text-xl font-bold text-white font-outfit mb-4">Shoulder Rehab</h3>
                <ul className="space-y-3 text-gray-400">
                  <li className="flex items-start gap-2"><div className="w-1.5 h-1.5 rounded-full bg-[#F5C518] mt-2" /> Frozen Shoulder</li>
                  <li className="flex items-start gap-2"><div className="w-1.5 h-1.5 rounded-full bg-[#F5C518] mt-2" /> Stiffness Relief</li>
                  <li className="flex items-start gap-2"><div className="w-1.5 h-1.5 rounded-full bg-[#F5C518] mt-2" /> Rotator Cuff</li>
                  <li className="flex items-start gap-2"><div className="w-1.5 h-1.5 rounded-full bg-[#F5C518] mt-2" /> Hydrodilatation</li>
                </ul>
              </div>
            </div>

            {/* Spine & Nerve */}
            <div className="bento-card gold-glow-hover rounded-2xl p-8 flex flex-col justify-between group">
              <div>
                <div className="w-14 h-14 bg-[#111] border border-[#F5C518]/30 rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                  <Brain className="w-7 h-7 text-[#F5C518]" />
                </div>
                <h3 className="text-xl font-bold text-white font-outfit mb-4">Spine & Nerve</h3>
                <ul className="space-y-3 text-gray-400">
                  <li className="flex items-start gap-2"><div className="w-1.5 h-1.5 rounded-full bg-[#F5C518] mt-2" /> Cervical Spondylosis</li>
                  <li className="flex items-start gap-2"><div className="w-1.5 h-1.5 rounded-full bg-[#F5C518] mt-2" /> Lumbar Spondylosis</li>
                  <li className="flex items-start gap-2"><div className="w-1.5 h-1.5 rounded-full bg-[#F5C518] mt-2" /> Nerve Compression</li>
                </ul>
              </div>
            </div>

            {/* Sports & Ortho - Tall */}
            <div className="bento-card gold-glow-hover rounded-2xl p-8 lg:row-span-2 flex flex-col group">
              <div className="w-14 h-14 bg-[#111] border border-[#F5C518]/30 rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <Dumbbell className="w-7 h-7 text-[#F5C518]" />
              </div>
              <h3 className="text-2xl font-bold text-white font-outfit mb-4">Sports & Orthopaedic</h3>
              <p className="text-gray-400 mb-6">Expert rehabilitation for athletes and post-surgical recovery.</p>
              <div className="space-y-4 flex-grow">
                {[
                  { name: 'Sports Injury', desc: 'Return to play faster and stronger' },
                  { name: 'ACL & Meniscus', desc: 'Knee ligament specialized rehab' },
                  { name: 'Fracture Rehab', desc: 'Regain mobility and strength' },
                  { name: 'Post-Surgery', desc: 'Guided recovery protocols' }
                ].map(item => (
                  <div key={item.name} className="bg-[#111] p-4 rounded-xl border border-gray-800">
                    <h4 className="text-white font-medium">{item.name}</h4>
                    <p className="text-sm text-gray-500 mt-1">{item.desc}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Advanced Treatments */}
            <div className="bento-card gold-glow-hover rounded-2xl p-8 flex flex-col justify-between group">
              <div>
                <div className="w-14 h-14 bg-[#111] border border-[#F5C518]/30 rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                  <Syringe className="w-7 h-7 text-[#F5C518]" />
                </div>
                <h3 className="text-xl font-bold text-white font-outfit mb-4">Advanced Tech</h3>
                <div className="flex flex-wrap gap-2">
                  {['Dry Needling', 'Cupping', 'Kinesio Taping', 'Electrotherapy', 'Ultrasound', 'Manual Therapy'].map(item => (
                    <span key={item} className="px-3 py-1 bg-[#111] border border-gray-800 text-sm rounded-full text-gray-300">{item}</span>
                  ))}
                </div>
              </div>
            </div>

            {/* Neurological */}
            <div className="bento-card gold-glow-hover rounded-2xl p-8 flex flex-col justify-between group">
              <div>
                <div className="w-14 h-14 bg-[#111] border border-[#F5C518]/30 rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                  <HeartPulse className="w-7 h-7 text-[#F5C518]" />
                </div>
                <h3 className="text-xl font-bold text-white font-outfit mb-4">Neurological</h3>
                <ul className="space-y-3 text-gray-400">
                  <li className="flex items-start gap-2"><div className="w-1.5 h-1.5 rounded-full bg-[#F5C518] mt-2" /> Stroke Rehab</li>
                  <li className="flex items-start gap-2"><div className="w-1.5 h-1.5 rounded-full bg-[#F5C518] mt-2" /> Paralysis Physio</li>
                  <li className="flex items-start gap-2"><div className="w-1.5 h-1.5 rounded-full bg-[#F5C518] mt-2" /> Parkinson's Care</li>
                </ul>
              </div>
            </div>

            {/* Women's Health & Home Care - Split Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 lg:col-span-2">
              <div className="bento-card gold-glow-hover rounded-2xl p-8 group">
                <div className="w-12 h-12 bg-[#111] border border-[#F5C518]/30 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                  <Stethoscope className="w-6 h-6 text-[#F5C518]" />
                </div>
                <h3 className="text-xl font-bold text-white font-outfit mb-3">Women's Health</h3>
                <p className="text-gray-400 text-sm mb-4">Pregnancy physio, postpartum recovery, and pelvic floor strengthening.</p>
              </div>
              
              <div className="bento-card gold-glow-hover rounded-2xl p-8 group">
                <div className="w-12 h-12 bg-[#111] border border-[#F5C518]/30 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                  <Home className="w-6 h-6 text-[#F5C518]" />
                </div>
                <h3 className="text-xl font-bold text-white font-outfit mb-3">Home Care</h3>
                <p className="text-gray-400 text-sm mb-4">Home visit physio, elderly care, and post-surgery home rehabilitation.</p>
              </div>
            </div>

          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-24 bg-[#151515] relative overflow-hidden">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-[#F5C518] rounded-full blur-[200px] opacity-[0.03] pointer-events-none" />
        
        <div className="max-w-7xl mx-auto px-6 relative z-10">
          <div className="text-center mb-16">
            <h2 className="text-4xl lg:text-5xl font-bold text-white font-outfit mb-4">How It <span className="gold-gradient-text">Works</span></h2>
            <p className="text-gray-400 max-w-2xl mx-auto text-lg">A systematic approach to your recovery journey.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            {[
              { icon: ClipboardList, title: "1. Assessment", desc: "Detailed evaluation of your condition and medical history." },
              { icon: Crosshair, title: "2. Diagnosis", desc: "Identifying the root cause, not just the symptoms." },
              { icon: Activity, title: "3. Treatment", desc: "Customized therapy using advanced techniques." },
              { icon: CheckCircle2, title: "4. Recovery", desc: "Guided exercises for long-term health and prevention." }
            ].map((step, idx) => (
              <div key={idx} className="relative text-center">
                <div className="w-20 h-20 mx-auto bg-[#1A1A1A] border-2 border-[#F5C518] rounded-2xl flex items-center justify-center mb-6 rotate-3 hover:rotate-0 transition-transform gold-glow">
                  <step.icon className="w-8 h-8 text-[#F5C518]" />
                </div>
                <h3 className="text-xl font-bold text-white font-outfit mb-2">{step.title}</h3>
                <p className="text-gray-400">{step.desc}</p>
                {idx < 3 && <div className="hidden md:block absolute top-10 right-0 w-1/2 h-0.5 bg-gradient-to-r from-[#F5C518]/50 to-transparent translate-x-1/2" />}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24 relative">
        <div className="max-w-5xl mx-auto px-6">
          <div className="bg-[#1A1A1A] rounded-3xl p-10 md:p-16 border border-[#F5C518]/20 relative overflow-hidden text-center md:text-left flex flex-col md:flex-row items-center justify-between gap-10">
            <div className="absolute right-0 top-0 w-64 h-64 bg-[#F5C518] blur-[100px] opacity-10 rounded-full translate-x-1/2 -translate-y-1/2" />
            
            <div className="relative z-10 max-w-xl">
              <h2 className="text-3xl md:text-4xl font-bold text-white font-outfit mb-4">
                Ready to start your <span className="gold-gradient-text">recovery journey?</span>
              </h2>
              <p className="text-gray-400 text-lg mb-0">
                Book an appointment with Dr. Dhvani Patalia today and take the first step towards a pain-free life.
              </p>
            </div>
            
            <div className="relative z-10 shrink-0 w-full md:w-auto">
              <button className="w-full md:w-auto px-10 py-5 bg-[#F5C518] text-[#111] font-bold rounded-xl hover:bg-[#D4A017] hover:scale-105 transition-all flex items-center justify-center gap-3 text-lg group">
                Book Consultation
                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
