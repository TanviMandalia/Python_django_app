import React from 'react';
import { 
  Activity, 
  Bone, 
  Brain, 
  Dumbbell, 
  Heart, 
  Zap, 
  Move, 
  Home, 
  ShieldAlert,
  ArrowRight,
  CheckCircle2,
  Calendar,
  ClipboardList,
  Stethoscope,
  Smile
} from 'lucide-react';

const services = [
  {
    id: 1,
    title: 'Pain Management',
    icon: ShieldAlert,
    iconColor: 'text-amber-500',
    iconBg: 'bg-amber-100',
    items: ['Neck Pain', 'Back Pain', 'Slip Disc', 'Sciatica', 'Shoulder Pain', 'Knee Pain', 'Joint Pain', 'Muscle Spasm'],
  },
  {
    id: 2,
    title: 'Frozen Shoulder & Shoulder Rehab',
    icon: Bone,
    iconColor: 'text-blue-500',
    iconBg: 'bg-blue-100',
    items: ['Frozen Shoulder', 'Shoulder Stiffness', 'Rotator Cuff', 'Hydrodilatation Rehab'],
  },
  {
    id: 3,
    title: 'Spine & Nerve Conditions',
    icon: Activity,
    iconColor: 'text-teal-500',
    iconBg: 'bg-teal-100',
    items: ['Cervical Spondylosis', 'Lumbar Spondylosis', 'Sciatica', 'Nerve Compression', 'Posture Correction'],
  },
  {
    id: 4,
    title: 'Sports & Orthopaedic',
    icon: Dumbbell,
    iconColor: 'text-orange-500',
    iconBg: 'bg-orange-100',
    items: ['Sports Injury', 'ACL Rehab', 'Meniscus Injury', 'Fracture Rehab', 'Ligament', 'Post-Surgery Physio'],
  },
  {
    id: 5,
    title: 'Neurological',
    icon: Brain,
    iconColor: 'text-purple-500',
    iconBg: 'bg-purple-100',
    items: ['Stroke Rehab', 'Paralysis Physio', 'Parkinson\'s', 'Balance & Gait Training'],
  },
  {
    id: 6,
    title: 'Women\'s Health',
    icon: Heart,
    iconColor: 'text-pink-500',
    iconBg: 'bg-pink-100',
    items: ['Pregnancy Physio', 'Postpartum Recovery', 'Pelvic Floor'],
  },
  {
    id: 7,
    title: 'Advanced Treatments',
    icon: Zap,
    iconColor: 'text-yellow-600',
    iconBg: 'bg-yellow-100',
    items: ['Dry Needling', 'Cupping', 'Kinesiology Taping', 'Electrotherapy', 'IFT/TENS', 'Ultrasound', 'Manual Therapy', 'Myofascial Release'],
  },
  {
    id: 8,
    title: 'Mobility & Fitness',
    icon: Move,
    iconColor: 'text-indigo-500',
    iconBg: 'bg-indigo-100',
    items: ['Strengthening', 'Flexibility', 'Posture Correction', 'Ergonomics', 'Functional Rehab'],
  },
  {
    id: 9,
    title: 'Home Care',
    icon: Home,
    iconColor: 'text-emerald-500',
    iconBg: 'bg-emerald-100',
    items: ['Home Visit Physio', 'Elderly Home Physio', 'Post-Surgery Home Rehab'],
  }
];

const steps = [
  {
    id: 1,
    title: 'Consultation',
    description: 'Initial assessment to understand your pain, history, and goals.',
    icon: Stethoscope,
  },
  {
    id: 2,
    title: 'Custom Plan',
    description: 'A tailored rehabilitation program designed specifically for your needs.',
    icon: ClipboardList,
  },
  {
    id: 3,
    title: 'Active Therapy',
    description: 'Hands-on treatment and guided exercises to restore mobility and strength.',
    icon: Activity,
  },
  {
    id: 4,
    title: 'Recovery & Beyond',
    description: 'Ongoing support, education, and maintenance to prevent future injuries.',
    icon: Smile,
  }
];

export function CardGrid() {
  return (
    <div className="min-h-screen bg-stone-50 font-sans text-stone-800 selection:bg-[#F5C518] selection:text-stone-900">
      
      {/* Hero Section */}
      <section className="pt-32 pb-20 px-6 lg:px-12 max-w-7xl mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
          <div className="space-y-8">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-stone-200/50 border border-stone-200 text-stone-600 text-sm font-medium">
              <span className="w-2 h-2 rounded-full bg-[#F5C518]"></span>
              Comprehensive Physiotherapy
            </div>
            <h1 className="text-5xl lg:text-7xl font-bold tracking-tight text-[#2C2C2C] leading-tight">
              Restore your <br/>
              <span className="text-[#F5C518] italic pr-2">mobility,</span><br/>
              reclaim your life.
            </h1>
            <p className="text-xl text-stone-600 max-w-lg leading-relaxed">
              Dr. Dhvani Patalia Physio-Rehab provides advanced, evidence-based treatments tailored to your unique recovery journey in Jamnagar.
            </p>
            <div className="flex flex-wrap gap-4 pt-4">
              <button className="px-8 py-4 bg-[#2C2C2C] text-white font-medium rounded-xl hover:bg-stone-800 transition-colors flex items-center gap-2 shadow-lg shadow-stone-900/10">
                Book Appointment <ArrowRight className="w-5 h-5" />
              </button>
              <button className="px-8 py-4 bg-white text-[#2C2C2C] border-2 border-stone-200 font-medium rounded-xl hover:border-[#F5C518] transition-colors">
                View All Services
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 lg:gap-6">
            <div className="bg-white p-6 rounded-3xl shadow-sm border border-stone-100 flex flex-col justify-between aspect-square">
              <div className="w-12 h-12 bg-orange-100 text-orange-600 rounded-2xl flex items-center justify-center mb-4">
                <Brain className="w-6 h-6" />
              </div>
              <div>
                <div className="text-4xl font-bold text-[#2C2C2C] mb-1">10+</div>
                <div className="text-stone-500 font-medium text-sm">Years Experience</div>
              </div>
            </div>
            <div className="bg-[#2C2C2C] text-white p-6 rounded-3xl shadow-sm flex flex-col justify-between aspect-square translate-y-8">
              <div className="w-12 h-12 bg-stone-700 text-[#F5C518] rounded-2xl flex items-center justify-center mb-4">
                <Smile className="w-6 h-6" />
              </div>
              <div>
                <div className="text-4xl font-bold mb-1">5k+</div>
                <div className="text-stone-400 font-medium text-sm">Happy Patients</div>
              </div>
            </div>
            <div className="bg-[#F5C518] p-6 rounded-3xl shadow-sm flex flex-col justify-between aspect-square">
              <div className="w-12 h-12 bg-white/20 text-stone-900 rounded-2xl flex items-center justify-center mb-4">
                <Activity className="w-6 h-6" />
              </div>
              <div>
                <div className="text-4xl font-bold text-stone-900 mb-1">98%</div>
                <div className="text-stone-800 font-medium text-sm">Recovery Rate</div>
              </div>
            </div>
            <div className="bg-white p-6 rounded-3xl shadow-sm border border-stone-100 flex flex-col justify-between aspect-square translate-y-8">
              <div className="w-12 h-12 bg-emerald-100 text-emerald-600 rounded-2xl flex items-center justify-center mb-4">
                <Stethoscope className="w-6 h-6" />
              </div>
              <div>
                <div className="text-4xl font-bold text-[#2C2C2C] mb-1">15+</div>
                <div className="text-stone-500 font-medium text-sm">Advanced Therapies</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Services Grid */}
      <section className="py-24 bg-white relative">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#f5f5f4_1px,transparent_1px),linear-gradient(to_bottom,#f5f5f4_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)]"></div>
        <div className="max-w-7xl mx-auto px-6 lg:px-12 relative">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <h2 className="text-4xl font-bold text-[#2C2C2C] mb-4">Comprehensive Care</h2>
            <p className="text-lg text-stone-500">We offer a wide range of specialized physiotherapy services to address your specific conditions and help you achieve optimal physical health.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 md:gap-8 items-start">
            {services.map((service, index) => (
              <div 
                key={service.id} 
                className={`bg-white rounded-3xl p-8 shadow-sm border border-stone-100 hover:shadow-xl hover:border-stone-200 transition-all duration-300 group ${index % 3 === 1 ? 'lg:translate-y-12' : index % 3 === 2 ? 'lg:translate-y-6' : ''}`}
              >
                <div className={`w-14 h-14 rounded-2xl ${service.iconBg} ${service.iconColor} flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300`}>
                  <service.icon className="w-7 h-7" />
                </div>
                <h3 className="text-2xl font-bold text-[#2C2C2C] mb-6">{service.title}</h3>
                <div className="flex flex-wrap gap-2">
                  {service.items.map((item, i) => (
                    <span 
                      key={i} 
                      className="px-3 py-1.5 bg-stone-50 border border-stone-100 text-stone-600 text-sm font-medium rounded-lg hover:bg-stone-100 hover:text-stone-900 transition-colors cursor-default"
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-32 bg-stone-50 relative overflow-hidden">
        <div className="max-w-7xl mx-auto px-6 lg:px-12 relative z-10">
          <div className="text-center max-w-2xl mx-auto mb-20">
            <h2 className="text-4xl font-bold text-[#2C2C2C] mb-4">Your Journey to Recovery</h2>
            <p className="text-lg text-stone-500">A clear, structured approach to getting you back to your best self.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 relative">
            <div className="hidden lg:block absolute top-12 left-[10%] right-[10%] h-0.5 bg-gradient-to-r from-stone-200 via-[#F5C518] to-stone-200 z-0"></div>
            
            {steps.map((step, index) => (
              <div key={step.id} className="relative z-10 flex flex-col items-center text-center group">
                <div className="w-24 h-24 bg-white rounded-full flex items-center justify-center shadow-lg shadow-stone-200/50 mb-6 border-4 border-stone-50 group-hover:border-[#F5C518] transition-colors duration-300">
                  <step.icon className="w-10 h-10 text-[#2C2C2C]" />
                </div>
                <div className="text-sm font-bold text-[#F5C518] tracking-widest uppercase mb-2">Step 0{step.id}</div>
                <h3 className="text-xl font-bold text-[#2C2C2C] mb-3">{step.title}</h3>
                <p className="text-stone-500 leading-relaxed">{step.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24 px-6 lg:px-12 max-w-7xl mx-auto">
        <div className="relative rounded-3xl overflow-hidden bg-gradient-to-br from-[#2C2C2C] to-stone-900 px-8 py-16 lg:p-20 shadow-2xl">
          <div className="absolute top-0 right-0 w-[800px] h-[800px] bg-[#F5C518]/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/3 mix-blend-screen pointer-events-none"></div>
          
          <div className="relative z-10 flex flex-col lg:flex-row items-center justify-between gap-12">
            <div className="max-w-2xl text-center lg:text-left">
              <h2 className="text-4xl lg:text-5xl font-bold text-white mb-6 leading-tight">
                Ready to take the first step towards a pain-free life?
              </h2>
              <p className="text-xl text-stone-300 mb-8 max-w-xl">
                Schedule your consultation today and let us create a personalized treatment plan for you.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center lg:justify-start">
                <button className="px-8 py-4 bg-[#F5C518] text-stone-900 font-bold rounded-xl hover:bg-yellow-400 transition-colors shadow-[0_0_40px_rgba(245,197,24,0.3)] flex items-center justify-center gap-2">
                  <Calendar className="w-5 h-5" /> Schedule Visit
                </button>
                <button className="px-8 py-4 bg-white/10 text-white font-medium rounded-xl hover:bg-white/20 transition-colors border border-white/10 backdrop-blur-sm">
                  Call +91 98765 43210
                </button>
              </div>
            </div>
            
            <div className="hidden lg:flex w-72 h-72 rounded-full border border-white/20 items-center justify-center relative">
              <div className="absolute inset-4 rounded-full border border-white/10"></div>
              <div className="absolute inset-8 rounded-full border border-white/5 bg-white/5 backdrop-blur-sm flex items-center justify-center">
                <CheckCircle2 className="w-24 h-24 text-[#F5C518]" />
              </div>
            </div>
          </div>
        </div>
      </section>

    </div>
  );
}
