"""
Management command to seed clinical treatment categories and verified treatments
for Dr. Dhvani Patalia Physio Rehab in Jamnagar.
"""

from django.core.management.base import BaseCommand
from core.models import TreatmentCategory, Treatment, Review


TREATMENTS_DATA = [
    {
        "category": {
            "name": "Back Pain Treatment",
            "slug": "back-pain",
            "description": "Evidence-based spinal therapy for acute and chronic lumbar spine discomfort, disc bulges, and muscle spasms.",
            "icon_class": "fas fa-shield-alt",
            "order": 1,
        },
        "treatments": [
            {
                "name": "Lumbar Spine Rehabilitation & Disc Care",
                "slug": "lumbar-spine-rehabilitation",
                "short_description": "Targeted spinal decompressive therapy, core stability training, and manual joint mobilization for lower back pain.",
                "full_description": "Specialized physiotherapy for lower back pain, lumbar spondylosis, muscle spasms, and facet joint irritation. Our treatment identifies underlying spinal biomechanical faults and provides clinical relief through gentle spinal mobilization, core re-education, and postural alignment.",
                "symptoms": "Lower back stiffness, Dull aching in lumbar region, Sharp pain on bending, Muscle spasms, Inability to stand for long periods",
                "techniques": "Manual Joint Mobilization, Core Muscle Stabilization, McKenzie Method, IASTM, Pelvic Alignment",
                "duration": "45 - 60 Mins",
                "icon_class": "fas fa-shield-alt",
                "is_featured": True,
                "order": 1,
            }
        ],
    },
    {
        "category": {
            "name": "Frozen Shoulder Treatment",
            "slug": "frozen-shoulder",
            "description": "Systematic capsular release, graded mobilization, and rotator cuff therapy to restore full shoulder reach.",
            "icon_class": "fas fa-bone",
            "order": 2,
        },
        "treatments": [
            {
                "name": "Frozen Shoulder (Adhesive Capsulitis) Recovery",
                "slug": "frozen-shoulder-rehab",
                "short_description": "Graded shoulder joint mobilization and scapular rhythm restoration to eliminate stiffness and reclaim overhead reach.",
                "full_description": "Frozen shoulder causes severe joint stiffness, nocturnal ache, and restricted arm movements. Our clinical recovery protocol uses stage-matched capsular stretching, gentle joint glide techniques, and functional exercise therapy to restore normal glenohumeral movement.",
                "symptoms": "Inability to lift arm overhead, Difficulty dressing or combing hair, Severe night pain, Shoulder joint stiffness",
                "techniques": "Maitland Joint Mobilization, Capsular Stretching, Scapular Stabilization, Cryo-thermal Therapy, Therapeutic Ultrasound",
                "duration": "45 Mins",
                "icon_class": "fas fa-bone",
                "is_featured": True,
                "order": 2,
            }
        ],
    },
    {
        "category": {
            "name": "Knee Pain Treatment",
            "slug": "knee-pain",
            "description": "Non-surgical clinical care for osteoarthritis, patellofemoral syndrome, and ligamentous knee strains.",
            "icon_class": "fas fa-walking",
            "order": 3,
        },
        "treatments": [
            {
                "name": "Knee Osteoarthritis & Joint Care",
                "slug": "knee-osteoarthritis-joint-care",
                "short_description": "Targeted quadriceps strengthening, patellar mobilization, and gait alignment to reduce joint loading and eliminate pain.",
                "full_description": "Evidence-backed physiotherapy designed to preserve knee joint cartilage, strengthen peri-articular musculature, and improve walking tolerance. Suitable for knee osteoarthritis, meniscus recovery, runner's knee, and post-arthroscopy rehabilitation.",
                "symptoms": "Knee pain during climbing stairs, Crepitus or popping sensation, Morning knee stiffness, Difficulty squatting or standing up",
                "techniques": "VMO Muscle Activation, Patellar Mobilization, Closed Kinetic Chain Exercises, Interferential Therapy (IFT), Low-impact Cycling",
                "duration": "45 - 60 Mins",
                "icon_class": "fas fa-walking",
                "is_featured": True,
                "order": 3,
            }
        ],
    },
    {
        "category": {
            "name": "Numbness and Tingling",
            "slug": "numbness-tingling",
            "description": "Neurological mobilization and decompression therapy for peripheral nerve entrapments and radiculopathies.",
            "icon_class": "fas fa-hand-sparkles",
            "order": 4,
        },
        "treatments": [
            {
                "name": "Peripheral Nerve Decompression & Neuro-Dynamics",
                "slug": "nerve-decompression-neurodynamics",
                "short_description": "Targeted nerve flossing and spinal decompression to alleviate tingling, burning sensation, and hand/foot numbness.",
                "full_description": "Numbness, pins-and-needles, and burning sensations in the hands or feet often stem from compressed nerves in the spine or peripheral tunnels (such as Carpal Tunnel Syndrome or Tarsal Tunnel). We restore normal neural glide and relieve nerve irritation safely.",
                "symptoms": "Pins and needles in fingers or toes, Burning sensations, Loss of fine grip sensation, Night-time hand tingling",
                "techniques": "Neurodynamic Sliders and Tensioners, Cervical/Lumbar Traction, Myofascial Tunnel Release, Ergonomic Modification",
                "duration": "45 Mins",
                "icon_class": "fas fa-hand-sparkles",
                "is_featured": False,
                "order": 4,
            }
        ],
    },
    {
        "category": {
            "name": "Heel Pain Treatment",
            "slug": "heel-pain",
            "description": "Specialized clinical relief for plantar fasciitis, heel spurs, and Achilles tendonopathy.",
            "icon_class": "fas fa-shoe-prints",
            "order": 5,
        },
        "treatments": [
            {
                "name": "Plantar Fasciitis & Heel Spur Relief",
                "slug": "plantar-fasciitis-heel-spur-relief",
                "short_description": "Deep plantar fascia release, calf lengthening, and foot arch biomechanical correction to eliminate sharp morning heel pain.",
                "full_description": "Sharp pain on taking the first morning steps is the classic hallmark of plantar fasciitis. Our specialized heel protocol addresses calf tightness, intrinsic foot muscle weakness, and plantar fascia inflammation to produce rapid, long-lasting relief.",
                "symptoms": "Sharp heel pain upon waking, Pain after prolonged standing, Tenderness at bottom of heel bone, Arch soreness",
                "techniques": "Plantar Fascia Soft Tissue Release, Calf Eccentric Loading, Arch Taping, Deep Friction Massage, Therapeutic Ultrasound",
                "duration": "40 Mins",
                "icon_class": "fas fa-shoe-prints",
                "is_featured": True,
                "order": 5,
            }
        ],
    },
    {
        "category": {
            "name": "Posture Correction",
            "slug": "posture-correction",
            "description": "Ergonomic realignments, thoracic mobility, and muscle rebalancing for desk workers and students.",
            "icon_class": "fas fa-user-check",
            "order": 6,
        },
        "treatments": [
            {
                "name": "Postural Realignment & Tech-Neck Correction",
                "slug": "postural-realignment-tech-neck",
                "short_description": "Corrective exercises and spinal realignment to reverse forward head posture, rounded shoulders, and upper back slouching.",
                "full_description": "Long hours sitting at computers or looking down at smartphones create muscular imbalances: tight chest muscles, weak deep neck flexors, and a rounded upper spine. Our structured postural program restores natural spinal curves and eliminates postural strain.",
                "symptoms": "Forward head posture ('tech neck'), Rounded shoulders, Upper back fatigue, Postural headaches, Slouched sitting habit",
                "techniques": "Thoracic Extension Exercises, Scapular Retraction Training, Deep Cervical Flexor Activation, Ergonomic Desk Assessment",
                "duration": "45 Mins",
                "icon_class": "fas fa-user-check",
                "is_featured": True,
                "order": 6,
            }
        ],
    },
    {
        "category": {
            "name": "Cervical Spondylosis",
            "slug": "cervical-spondylosis",
            "description": "Gentle cervical mobilization and neck muscle reconditioning to relieve chronic neck pain and radiation.",
            "icon_class": "fas fa-head-side-cough",
            "order": 7,
        },
        "treatments": [
            {
                "name": "Cervical Spine Care & Neck Pain Management",
                "slug": "cervical-spine-care-neck-pain",
                "short_description": "Evidence-based neck mobilization, cervical traction, and muscle release to relieve neck stiffness and radiating shoulder discomfort.",
                "full_description": "Cervical spondylosis is age- or posture-related wear and tear of the neck vertebrae and discs. Our gentle clinical approach restores neck range of motion, relieves nerve pinch, and prevents headaches stemming from upper cervical joint restrictions.",
                "symptoms": "Neck stiffness when turning head, Radiating pain down the arm, Frequent tension headaches, Shoulder blade ache",
                "techniques": "Gentle Cervical Mobilization, Isometric Neck Strengthening, Gentle Intermittent Traction, Trapezius Trigger Point Release",
                "duration": "45 Mins",
                "icon_class": "fas fa-head-side-cough",
                "is_featured": True,
                "order": 7,
            }
        ],
    },
    {
        "category": {
            "name": "Sciatica Treatment",
            "slug": "sciatica",
            "description": "Targeted nerve flossing and spinal decompression to relieve sharp radiating leg pain and lumbar irritation.",
            "icon_class": "fas fa-bolt",
            "order": 8,
        },
        "treatments": [
            {
                "name": "Sciatic Nerve Decompression & Lumbar Protocol",
                "slug": "sciatic-nerve-decompression",
                "short_description": "Spinal decompression, piriformis muscle release, and sciatic nerve glides to eliminate radiating pain traveling down the leg.",
                "full_description": "Sciatica occurs when the sciatic nerve is pinched or inflamed in the lower back or piriformis muscle. Our targeted protocol reduces nerve compression, centralizes radiating symptoms back up to the spine, and guides patients to safe daily function without surgery.",
                "symptoms": "Sharp, shooting pain down one leg, Tingling or numbness below the knee, Pain aggravated by sitting, Weakness in leg",
                "techniques": "Sciatic Nerve Gliding (Neurodynamics), Lumbar Flexion/Extension Protocols, Piriformis Release, Pelvic Alignment",
                "duration": "50 Mins",
                "icon_class": "fas fa-bolt",
                "is_featured": True,
                "order": 8,
            }
        ],
    },
    {
        "category": {
            "name": "Vertigo Treatment",
            "slug": "vertigo",
            "description": "Vestibular rehabilitation therapy and canalith repositioning for balance disorders and BPPV.",
            "icon_class": "fas fa-compass",
            "order": 9,
        },
        "treatments": [
            {
                "name": "Vestibular Rehabilitation Therapy (VRT) & BPPV Care",
                "slug": "vestibular-rehabilitation-vertigo",
                "short_description": "Clinical repositioning maneuvers (Epley) and vestibular habituation exercises to resolve spinning sensations and restore equilibrium.",
                "full_description": "Benign Paroxysmal Positional Vertigo (BPPV) and inner ear disturbances cause intense spinning sensations and loss of balance when turning the head. Our certified clinical assessment identifies the affected semicircular canal and utilizes precise repositioning maneuvers for rapid recovery.",
                "symptoms": "Spinning sensation when turning head in bed, Unsteadiness when walking, Mild nausea, Dizziness on sudden head movement",
                "techniques": "Epley Maneuver, Semont Maneuver, Vestibular Ocular Reflex (VOR) Training, Balance & Equilibrium Retraining",
                "duration": "40 Mins",
                "icon_class": "fas fa-compass",
                "is_featured": False,
                "order": 9,
            }
        ],
    },
    {
        "category": {
            "name": "Muscle Pain Treatment",
            "slug": "muscle-pain",
            "description": "Myofascial release, dry needling, cupping therapy, and trigger point deactivation for acute and chronic muscular strains.",
            "icon_class": "fas fa-spa",
            "order": 10,
        },
        "treatments": [
            {
                "name": "Myofascial Release, Cupping & Trigger Point Therapy",
                "slug": "myofascial-release-cupping-therapy",
                "short_description": "Advanced integrative manual therapies to eliminate chronic myofascial trigger points, deep knots, and tight muscle bands.",
                "full_description": "Chronic muscle pain, tightness, and stubborn knots often develop from sustained muscular contractions, repetitive stress, or trauma. We combine medical cupping, instrument-assisted soft tissue mobilization (IASTM), and trigger point therapy to restore fluid muscle movement.",
                "symptoms": "Deep muscular aching, Painful knots in back and neck, Tight band sensation, Reduced muscular flexibility",
                "techniques": "Myofascial Release (MFR), Therapeutic Cupping, Dry Needling, Trigger Point Pressure Release, Heat Modalities",
                "duration": "45 Mins",
                "icon_class": "fas fa-spa",
                "is_featured": True,
                "order": 10,
            }
        ],
    },
]


class Command(BaseCommand):
    help = "Seeds standard clinical treatment categories and verified treatments for Dr. Dhvani Patalia Physio Rehab."

    def handle(self, *args, **options):
        self.stdout.write("Seeding treatment categories and treatments...")
        created_cats = 0
        created_treatments = 0

        for item in TREATMENTS_DATA:
            cat_data = item["category"]
            category, created = TreatmentCategory.objects.get_or_create(
                slug=cat_data["slug"],
                defaults={
                    "name": cat_data["name"],
                    "description": cat_data["description"],
                    "icon_class": cat_data["icon_class"],
                    "order": cat_data["order"],
                    "is_active": True,
                },
            )
            if created:
                created_cats += 1

            for t_data in item["treatments"]:
                treatment, t_created = Treatment.objects.get_or_create(
                    slug=t_data["slug"],
                    defaults={
                        "category": category,
                        "name": t_data["name"],
                        "short_description": t_data["short_description"],
                        "full_description": t_data["full_description"],
                        "symptoms": t_data["symptoms"],
                        "techniques": t_data["techniques"],
                        "duration": t_data["duration"],
                        "icon_class": t_data["icon_class"],
                        "is_featured": t_data.get("is_featured", False),
                        "order": t_data["order"],
                        "is_active": True,
                    },
                )
                if t_created:
                    created_treatments += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully processed treatments: {created_cats} categories created, {created_treatments} treatments created."
            )
        )
