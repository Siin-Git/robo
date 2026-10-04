import {render,screen,cleanup} from '@testing-library/react';
import {afterEach,describe,it,expect,vi} from 'vitest';
import {StrategyCatalog} from '@/components/strategies/StrategyCatalog';
const state=vi.hoisted(()=>({error:false}));
vi.mock('@tanstack/react-query',()=>({useQuery:()=>({isLoading:false,isError:state.error,refetch:vi.fn(),data:{items:[{id:'leader_stock',label:'주도주 모델'},{id:'export_stock',label:'수출 모델'}]}})}));
afterEach(()=>{cleanup();state.error=false;});
describe('research-only strategies',()=>{
  it('links source research without an activation control',()=>{
    render(<StrategyCatalog/>);
    expect(screen.getByRole('link',{name:'주도주 모델 · 자료 검토'})).toHaveAttribute('href','/strategies?strategy=leader_stock');
    expect(screen.getByRole('link',{name:'수출 모델 · 자료 검토'})).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    expect(screen.getByText(/Frontier·확정·자동 운용/)).toBeInTheDocument();
  });
  it('does not present failed source loading as an empty successful catalog',()=>{
    state.error=true;render(<StrategyCatalog/>);
    expect(screen.getByRole('alert')).toHaveTextContent('전략 자료 조회 실패');
    expect(screen.getByRole('button',{name:'다시 조회'})).toBeInTheDocument();
  });
});
