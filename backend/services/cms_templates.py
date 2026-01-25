"""
CMS Page Templates
Pre-built templates for common page types with one-click application
"""

# ============================================
# Landing Page Template
# ============================================

LANDING_PAGE_TEMPLATE = {
    "name": "Landing Page",
    "description": "A conversion-focused landing page with hero, features, testimonials, and CTA",
    "thumbnail": "landing-page-template.png",
    "blocks": [
        {
            "block_type": "HERO",
            "content": {
                "headline": "Transform Your Business Today",
                "subheadline": "Discover how our platform can help you achieve your goals faster and more efficiently than ever before.",
                "cta_text": "Get Started Free",
                "cta_link": "/signup",
                "secondary_cta_text": "Learn More",
                "secondary_cta_link": "#features",
                "alignment": "center"
            },
            "visible": True
        },
        {
            "block_type": "STATS_BAR",
            "content": {
                "stats": [
                    {"value": "10K+", "label": "Happy Customers"},
                    {"value": "99.9%", "label": "Uptime"},
                    {"value": "24/7", "label": "Support"},
                    {"value": "50+", "label": "Integrations"}
                ]
            },
            "visible": True
        },
        {
            "block_type": "FEATURES_GRID",
            "content": {
                "title": "Why Choose Us",
                "subtitle": "Everything you need to succeed, all in one place",
                "features": [
                    {
                        "icon": "Shield",
                        "title": "Enterprise Security",
                        "description": "Bank-level encryption and compliance with industry standards to keep your data safe."
                    },
                    {
                        "icon": "Zap",
                        "title": "Lightning Fast",
                        "description": "Optimized performance ensures your workflow stays smooth and responsive."
                    },
                    {
                        "icon": "Users",
                        "title": "Team Collaboration",
                        "description": "Work together seamlessly with real-time updates and shared workspaces."
                    },
                    {
                        "icon": "BarChart",
                        "title": "Analytics & Insights",
                        "description": "Make data-driven decisions with comprehensive reporting tools."
                    },
                    {
                        "icon": "Clock",
                        "title": "Save Time",
                        "description": "Automate repetitive tasks and focus on what matters most."
                    },
                    {
                        "icon": "Heart",
                        "title": "Customer Support",
                        "description": "Dedicated support team available around the clock to help you succeed."
                    }
                ],
                "columns": 3
            },
            "visible": True
        },
        {
            "block_type": "TESTIMONIALS",
            "content": {
                "title": "What Our Customers Say",
                "testimonials": [
                    {
                        "quote": "This platform has completely transformed how we operate. We've seen a 40% increase in productivity.",
                        "author_name": "Sarah Johnson",
                        "author_title": "CEO",
                        "author_company": "TechStart Inc.",
                        "rating": 5
                    },
                    {
                        "quote": "The best investment we've made for our business. The ROI was evident within the first month.",
                        "author_name": "Michael Chen",
                        "author_title": "Operations Director",
                        "author_company": "Growth Labs",
                        "rating": 5
                    },
                    {
                        "quote": "Incredible support and a product that just works. Highly recommend to any growing business.",
                        "author_name": "Emily Rodriguez",
                        "author_title": "Founder",
                        "author_company": "Bright Solutions",
                        "rating": 5
                    }
                ],
                "style": "cards"
            },
            "visible": True
        },
        {
            "block_type": "CTA",
            "content": {
                "headline": "Ready to Get Started?",
                "description": "Join thousands of businesses already transforming their operations.",
                "button_text": "Get Started",
                "button_link": "/signup",
                "style": "primary"
            },
            "visible": True
        }
    ]
}


# ============================================
# About Us Template
# ============================================

ABOUT_US_TEMPLATE = {
    "name": "About Us",
    "description": "Tell your company story with mission, team, and values sections",
    "thumbnail": "about-us-template.png",
    "blocks": [
        {
            "block_type": "HERO",
            "content": {
                "headline": "About Our Company",
                "subheadline": "We're on a mission to make compliance simple, accessible, and stress-free for property owners everywhere.",
                "alignment": "center"
            },
            "visible": True
        },
        {
            "block_type": "TEXT_BLOCK",
            "content": {
                "title": "Our Story",
                "body": "Founded in 2020, we set out to solve a problem that frustrated property owners across the UK: keeping track of compliance requirements was complex, time-consuming, and often resulted in missed deadlines.\n\nOur founders, having experienced these challenges firsthand, built a platform that automates compliance tracking, sends timely reminders, and provides peace of mind to landlords and property managers.\n\nToday, we serve thousands of properties and continue to innovate, making compliance management effortless for everyone.",
                "alignment": "left"
            },
            "visible": True
        },
        {
            "block_type": "STATS_BAR",
            "content": {
                "stats": [
                    {"value": "2020", "label": "Founded"},
                    {"value": "50+", "label": "Team Members"},
                    {"value": "10K+", "label": "Properties Managed"},
                    {"value": "UK", "label": "Headquarters"}
                ]
            },
            "visible": True
        },
        {
            "block_type": "FEATURES_GRID",
            "content": {
                "title": "Our Values",
                "subtitle": "The principles that guide everything we do",
                "features": [
                    {
                        "icon": "Target",
                        "title": "Customer First",
                        "description": "Every decision we make starts with asking: how does this help our customers succeed?"
                    },
                    {
                        "icon": "Shield",
                        "title": "Trust & Security",
                        "description": "We handle sensitive data with the utmost care and maintain the highest security standards."
                    },
                    {
                        "icon": "Lightbulb",
                        "title": "Continuous Innovation",
                        "description": "We're always looking for better ways to solve problems and improve our platform."
                    },
                    {
                        "icon": "Heart",
                        "title": "Empathy",
                        "description": "We understand the challenges our users face and build solutions that truly help."
                    }
                ],
                "columns": 2
            },
            "visible": True
        },
        {
            "block_type": "TEAM_SECTION",
            "content": {
                "title": "Meet Our Leadership",
                "members": [
                    {
                        "name": "Jane Smith",
                        "role": "Chief Executive Officer",
                        "bio": "15+ years in proptech, previously at PropertyCloud."
                    },
                    {
                        "name": "John Davies",
                        "role": "Chief Technology Officer",
                        "bio": "Former engineering lead at a FTSE 100 company."
                    },
                    {
                        "name": "Sarah Williams",
                        "role": "Chief Operations Officer",
                        "bio": "Background in scaling operations at high-growth startups."
                    },
                    {
                        "name": "David Brown",
                        "role": "Chief Customer Officer",
                        "bio": "Passionate about customer success and building great experiences."
                    }
                ]
            },
            "visible": True
        },
        {
            "block_type": "CTA",
            "content": {
                "headline": "Join Our Journey",
                "description": "We're always looking for talented people to join our team.",
                "button_text": "View Open Positions",
                "button_link": "/careers",
                "style": "secondary"
            },
            "visible": True
        }
    ]
}


# ============================================
# Contact Us Template
# ============================================

CONTACT_US_TEMPLATE = {
    "name": "Contact Us",
    "description": "Contact page with form, office locations, and support options",
    "thumbnail": "contact-us-template.png",
    "blocks": [
        {
            "block_type": "HERO",
            "content": {
                "headline": "Get in Touch",
                "subheadline": "We'd love to hear from you. Our team is here to help with any questions.",
                "alignment": "center"
            },
            "visible": True
        },
        {
            "block_type": "FEATURES_GRID",
            "content": {
                "title": "How Can We Help?",
                "features": [
                    {
                        "icon": "MessageCircle",
                        "title": "Sales Enquiries",
                        "description": "Interested in our services? Talk to our sales team about your needs."
                    },
                    {
                        "icon": "Headphones",
                        "title": "Customer Support",
                        "description": "Already a customer? Our support team is available 24/7 to help."
                    },
                    {
                        "icon": "Building",
                        "title": "Partnerships",
                        "description": "Interested in partnering with us? Let's explore opportunities together."
                    }
                ],
                "columns": 3
            },
            "visible": True
        },
        {
            "block_type": "CONTACT_FORM",
            "content": {
                "title": "Send Us a Message",
                "subtitle": "Fill out the form below and we'll get back to you within 24 hours.",
                "fields": ["name", "email", "phone", "company", "message"],
                "submit_button_text": "Send Message",
                "success_message": "Thank you! We'll be in touch soon."
            },
            "visible": True
        },
        {
            "block_type": "TEXT_BLOCK",
            "content": {
                "title": "Our Office",
                "body": "**Pleerity Enterprise Ltd**\n\n123 Business Park\nLondon, EC2A 1AB\nUnited Kingdom\n\n**Email:** hello@pleerity.com\n**Phone:** +44 (0) 20 1234 5678\n\n**Hours:** Monday - Friday, 9am - 6pm GMT",
                "alignment": "left"
            },
            "visible": True
        },
        {
            "block_type": "FAQ",
            "content": {
                "title": "Frequently Asked Questions",
                "items": [
                    {
                        "question": "What are your support hours?",
                        "answer": "Our support team is available 24/7 for urgent issues. For general enquiries, we operate Monday to Friday, 9am to 6pm GMT."
                    },
                    {
                        "question": "How quickly do you respond to enquiries?",
                        "answer": "We aim to respond to all enquiries within 24 hours during business days. Urgent support tickets are typically addressed within 2 hours."
                    },
                    {
                        "question": "Can I schedule a demo?",
                        "answer": "Yes! You can schedule a personalised demo with our team by filling out the contact form above or emailing us directly."
                    }
                ]
            },
            "visible": True
        }
    ]
}


# ============================================
# Pricing Page Template
# ============================================

PRICING_PAGE_TEMPLATE = {
    "name": "Pricing Page",
    "description": "Showcase your pricing tiers with features comparison",
    "thumbnail": "pricing-template.png",
    "blocks": [
        {
            "block_type": "HERO",
            "content": {
                "headline": "Simple, Transparent Pricing",
                "subheadline": "Choose the plan that fits your needs. No hidden fees, no surprises.",
                "alignment": "center"
            },
            "visible": True
        },
        {
            "block_type": "PRICING_TABLE",
            "content": {
                "title": "Choose Your Plan",
                "subtitle": "Simple, transparent pricing for every portfolio size",
                "tiers": [
                    {
                        "name": "Starter",
                        "price": "£29/mo",
                        "description": "Perfect for individual landlords",
                        "features": [
                            "Up to 5 properties",
                            "Basic compliance tracking",
                            "Email reminders",
                            "Standard support"
                        ],
                        "cta_text": "Get Started",
                        "cta_link": "/signup?plan=starter",
                        "is_highlighted": False
                    },
                    {
                        "name": "Professional",
                        "price": "£79/mo",
                        "description": "For growing portfolios",
                        "features": [
                            "Up to 25 properties",
                            "Advanced compliance tracking",
                            "SMS & email reminders",
                            "Document storage",
                            "Priority support"
                        ],
                        "cta_text": "Get Started",
                        "cta_link": "/signup?plan=professional",
                        "is_highlighted": True
                    },
                    {
                        "name": "Enterprise",
                        "price": "Custom",
                        "description": "For large portfolios",
                        "features": [
                            "Unlimited properties",
                            "Full compliance suite",
                            "API access",
                            "Custom integrations",
                            "Dedicated account manager"
                        ],
                        "cta_text": "Contact Sales",
                        "cta_link": "/contact",
                        "is_highlighted": False
                    }
                ]
            },
            "visible": True
        },
        {
            "block_type": "FAQ",
            "content": {
                "title": "Pricing FAQs",
                "items": [
                    {
                        "question": "Can I change plans later?",
                        "answer": "Yes, you can upgrade or downgrade your plan at any time. Changes take effect on your next billing cycle."
                    },
                    {
                        "question": "What payment methods do you accept?",
                        "answer": "We accept all major credit cards, direct debit, and bank transfers for annual plans."
                    },
                    {
                        "question": "Is there a contract or commitment?",
                        "answer": "No long-term contracts. You can cancel anytime. Annual plans offer a 20% discount."
                    },
                    {
                        "question": "Do you offer discounts for charities?",
                        "answer": "Yes, we offer special pricing for registered charities and non-profits. Contact us to learn more."
                    }
                ]
            },
            "visible": True
        },
        {
            "block_type": "CTA",
            "content": {
                "headline": "Still Have Questions?",
                "description": "Our team is happy to help you find the perfect plan for your needs.",
                "button_text": "Talk to Sales",
                "button_link": "/contact",
                "style": "outline"
            },
            "visible": True
        }
    ]
}


# ============================================
# All Templates Export
# ============================================

CMS_TEMPLATES = {
    "landing_page": LANDING_PAGE_TEMPLATE,
    "about_us": ABOUT_US_TEMPLATE,
    "contact_us": CONTACT_US_TEMPLATE,
    "pricing_page": PRICING_PAGE_TEMPLATE,
}


def get_all_templates():
    """Get list of all available templates"""
    return [
        {
            "template_id": key,
            "name": template["name"],
            "description": template["description"],
            "block_count": len(template["blocks"]),
            "block_types": list(set(b["block_type"] for b in template["blocks"]))
        }
        for key, template in CMS_TEMPLATES.items()
    ]


def get_template(template_id: str):
    """Get a specific template by ID"""
    return CMS_TEMPLATES.get(template_id)
