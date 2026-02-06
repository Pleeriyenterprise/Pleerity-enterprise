import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Label } from '../../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Checkbox } from '../../components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Alert, AlertDescription } from '../../components/ui/alert';
import { ArrowRight, ArrowLeft, CheckCircle, AlertCircle } from 'lucide-react';

const TalentPoolWizard = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const [form, setForm] = useState({
    full_name: '', email: '', country: '', linkedin_url: '', phone: '',
    interest_areas: [], other_interest_text: '',
    professional_summary: '', years_experience: '',
    skills_tools: [], other_skills_text: '', availability: '', work_style: [],
    consent_accepted: false
  });

  const API_URL = process.env.REACT_APP_BACKEND_URL;

  const interests = ['AI Workflow Automation', 'Compliance & Documentation', 'Market Research & Analysis', 'Operations / Admin', 'Engineering / Technical', 'Front End / Back End Development', 'Other'];
  const skills = ['AI tools', 'Automation tools', 'Google Workspace', 'Microsoft 365', 'Zoho', 'Documentation & compliance', 'Jira / Trello / Asana', 'Stripe', 'Other'];

  const toggle = (field, val) => {
    setForm(prev => ({
      ...prev,
      [field]: prev[field].includes(val) ? prev[field].filter(i => i !== val) : [...prev[field], val]
    }));
  };

  const validate = () => {
    if (step === 1 && (!form.full_name || !form.email || !form.country)) return 'Fill all required fields';
    if (step === 2 && form.interest_areas.length === 0) return 'Select at least one interest';
    if (step === 3 && (!form.professional_summary || !form.years_experience)) return 'Complete all fields';
    if (step === 4 && (!form.availability || form.work_style.length === 0 || !form.consent_accepted)) return 'Complete all fields and accept consent';
    return null;
  };

  const next = () => {
    const err = validate();
    if (err) { setError(err); return; }
    setError('');
    setStep(s => Math.min(s + 1, 4));
  };

  const prev = () => { setError(''); setStep(s => Math.max(s - 1, 1)); };

  const submit = async () => {
    const err = validate();
    if (err) { setError(err); return; }
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/talent-pool/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form)
      });
      if (res.ok) setSuccess(true);
      else setError('Submission failed');
    } catch { setError('Network error'); }
    finally { setLoading(false); }
  };

  if (success) {
    return (
      <PublicLayout>
        <div className="min-h-screen flex items-center justify-center py-20">
          <Card className="max-w-md">
            <CardContent className="pt-6 text-center">
              <CheckCircle className="w-16 h-16 text-green-600 mx-auto mb-4" />
              <h2 className="text-2xl font-bold mb-3">Thank You!</h2>
              <p className="text-gray-600 mb-6">Your details have been added to our Talent Pool.</p>
              <Button onClick={() => navigate('/careers')}>Back to Careers</Button>
            </CardContent>
          </Card>
        </div>
      </PublicLayout>
    );
  }

  return (
    <PublicLayout>
      <SEOHead title="Join Talent Pool" canonicalUrl="/careers/talent-pool" />
      <div className="max-w-3xl mx-auto px-4 py-12">
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            {[1,2,3,4].map(n => (
              <div key={n} className="flex-1 flex items-center">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold ${n <= step ? 'bg-electric-teal text-white' : 'bg-gray-200 text-gray-500'}`}>{n}</div>
                {n < 4 && <div className={`flex-1 h-1 mx-2 ${n < step ? 'bg-electric-teal' : 'bg-gray-200'}`} />}
              </div>
            ))}
          </div>
        </div>

        {error && <Alert variant="destructive" className="mb-6"><AlertCircle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription></Alert>}

        <Card>
          <CardHeader><CardTitle>Step {step} of 4</CardTitle></CardHeader>
          <CardContent>
            {step === 1 && (
              <div className="space-y-4">
                <div><Label>Full Name *</Label><Input value={form.full_name} onChange={e => setForm({...form, full_name: e.target.value})} /></div>
                <div><Label>Email *</Label><Input type="email" value={form.email} onChange={e => setForm({...form, email: e.target.value})} /></div>
                <div><Label>Country *</Label><Input value={form.country} onChange={e => setForm({...form, country: e.target.value})} /></div>
                <div><Label>LinkedIn</Label><Input value={form.linkedin_url} onChange={e => setForm({...form, linkedin_url: e.target.value})} /></div>
                <div><Label>Phone</Label><Input value={form.phone} onChange={e => setForm({...form, phone: e.target.value})} /></div>
              </div>
            )}

            {step === 2 && (
              <div className="space-y-3">
                <Label>Select interests *</Label>
                {interests.map(i => <div key={i} className="flex items-center space-x-2"><Checkbox checked={form.interest_areas.includes(i)} onCheckedChange={() => toggle('interest_areas', i)} /><label className="text-sm">{i}</label></div>)}
              </div>
            )}

            {step === 3 && (
              <div className="space-y-4">
                <div><Label>Professional Summary *</Label><Textarea value={form.professional_summary} onChange={e => setForm({...form, professional_summary: e.target.value})} className="min-h-[120px]" /></div>
                <div>
                  <Label>Years of Experience *</Label>
                  <Select value={form.years_experience} onValueChange={v => setForm({...form, years_experience: v})}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="0-1">0-1 years</SelectItem>
                      <SelectItem value="1-2">1-2 years</SelectItem>
                      <SelectItem value="3-5">3-5 years</SelectItem>
                      <SelectItem value="6-10">6-10 years</SelectItem>
                      <SelectItem value="10+">10+ years</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}

            {step === 4 && (
              <div className="space-y-4">
                <div>
                  <Label>Skills</Label>
                  <div className="space-y-2 border rounded p-3 max-h-48 overflow-y-auto">
                    {skills.map(s => <div key={s} className="flex items-center space-x-2"><Checkbox checked={form.skills_tools.includes(s)} onCheckedChange={() => toggle('skills_tools', s)} /><label className="text-sm">{s}</label></div>)}
                  </div>
                </div>
                <div>
                  <Label>Availability *</Label>
                  <Select value={form.availability} onValueChange={v => setForm({...form, availability: v})}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Immediately">Immediately</SelectItem>
                      <SelectItem value="2 weeks">2 weeks</SelectItem>
                      <SelectItem value="1 month">1 month</SelectItem>
                      <SelectItem value="2+ months">2+ months</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Work Style *</Label>
                  <div className="space-y-2">
                    {['Remote', 'Hybrid', 'Flexible'].map(s => <div key={s} className="flex items-center space-x-2"><Checkbox checked={form.work_style.includes(s)} onCheckedChange={() => toggle('work_style', s)} /><label className="text-sm">{s}</label></div>)}
                  </div>
                </div>
                <div className="flex items-start space-x-2 pt-4 border-t">
                  <Checkbox checked={form.consent_accepted} onCheckedChange={c => setForm({...form, consent_accepted: c})} />
                  <label className="text-sm">I understand this is not a job application *</label>
                </div>
              </div>
            )}

            <div className="flex justify-between mt-8 pt-6 border-t">
              <Button onClick={prev} disabled={step === 1} variant="outline"><ArrowLeft className="w-4 h-4 mr-2" />Back</Button>
              {step < 4 ? (
                <Button onClick={next} className="bg-electric-teal hover:bg-electric-teal/90">Next<ArrowRight className="w-4 h-4 ml-2" /></Button>
              ) : (
                <Button onClick={submit} disabled={loading} className="bg-electric-teal hover:bg-electric-teal/90">{loading ? 'Submitting...' : 'Submit'}</Button>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </PublicLayout>
  );
};

export default TalentPoolWizard;
