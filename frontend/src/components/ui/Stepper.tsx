type StepStatus = 'pending' | 'current' | 'done';

type StepItem = {
  label: string;
  detail: string;
  status: StepStatus;
};

export function Stepper({ steps }: { steps: StepItem[] }) {
  return (
    <div className='ui-stepper'>
      {steps.map((step) => (
        <article key={step.label} className={`ui-step ${step.status}`}>
          <strong>{step.label}</strong>
          <p>{step.detail}</p>
        </article>
      ))}
    </div>
  );
}
