from elegantrl.agent import *
from elegantrl.run import *
import torch 

def trade(data_dic, drl_lib, env, agent, mode='backtesting', **kwargs):
    
    if mode == 'backtesting':
        if 'price_ary' in data_dic and 'tech_ary' in data_dic and 'turbulence_ary'\
        in data_dic:
            price_ary = data_dic['price_ary']
            tech_ary = data_dic['tech_ary']
            turbulence_ary = data_dic['turbulence_ary']
        elif 'price_ary' in data_dic and 'tech_ary' in data_dic and 'turbulence_ary'\
        not in data_dic:
            price_ary = data_dic['price_ary']
            tech_ary = data_dic['tech_ary']
        else:
            raise ValueError('Invalid input data_dic!')

        env_config = {'price_ary':price_ary,
                'tech_ary':tech_ary,
                'turbulence_ary':turbulence_ary,
                'if_train':False}
        env_instance = env(config=env_config)
        net_dimension = kwargs.get('net_dimension', 2**7)
        cwd = kwargs.get('cwd','./'+str(agent))

        #trade using elegantrl
        if drl_lib == 'elegantrl':

            #select agent
            if agent == 'ppo':
                args = Arguments(agent=AgentPPO(), env=env_instance, if_on_policy=True)
            else:
                raise ValueError('Invalid agent input or the agent input is not \
                                 supported yet.')

            #load agent
            try:
                state_dim = env_instance.state_dim
                action_dim = env_instance.action_dim

                agent = args.agent
                net_dim = net_dimension

                agent.init(net_dim, state_dim, action_dim)
                agent.save_load_model(cwd=cwd, if_save=False)
                act = agent.act
                device = agent.device

            except:
                raise ValueError('Fail to load agent!')

            #trade on the trading env
            _torch = torch
            state = env_instance.reset()
            episode_returns = list()  # the cumulative_return / initial_account
            with _torch.no_grad():
                for i in range(env_instance.max_step):
                    s_tensor = _torch.as_tensor((state,), device=device)
                    a_tensor = act(s_tensor)  # action_tanh = act.forward()
                    action = a_tensor.detach().cpu().numpy()[0]  # not need detach(), because with torch.no_grad() outside
                    state, reward, done, _ = env_instance.step(action)

                    total_asset = env_instance.amount + (env_instance.price_ary[env_instance.day] * env_instance.stocks).sum()
                    episode_return = total_asset / env_instance.initial_total_asset
                    episode_returns.append(episode_return)
                    if done:
                        break
            print('Test Finished!')
            #return episode returns on testing data
            return episode_returns

    elif mode == 'paper_trading':
        
        #trade using rllib
        elif drl_lib == 'rllib':
            #load agent
            from ray.rllib.agents import ppo
            from ray.rllib.agents.ppo.ppo import PPOTrainer
            config = ppo.DEFAULT_CONFIG.copy()
            config['env'] = env
            config["log_level"] = "WARN"
            config['env_config'] = {'price_ary':price_ary,
                                    'tech_ary':tech_ary,
                                    'turbulence_ary':turbulence_ary,
                                    'if_train':False}

            trainer = PPOTrainer(env=env, config=config)
            try:
                trainer.restore(cwd)
                print("Restoring from checkpoint path", cwd)
            except:
                raise ValueError('Fail to load agent!')

            #trade on the trading env
            state = env_instance.reset()
            episode_returns = list()  # the cumulative_return / initial_account
            done = False
            while not done:
                action = trainer.compute_single_action(state)
                state, reward, done, _ = env_instance.step(action)

                total_asset = env_instance.amount + (env_instance.price_ary[env_instance.day] * env_instance.stocks).sum()
                episode_return = total_asset / env_instance.initial_total_asset
                episode_returns.append(episode_return)
            print('episode return: ' + str(episode_return))
            print('Test Finished!')   
            return episode_returns

        #trade using stable baselines3
        elif drl_lib == 'stable_baselines3':
            from stable_baselines3 import PPO

            try:
                #load agent
                model = PPO.load(cwd)
                print("Successfully load model", cwd)
            except:
                raise ValueError('Fail to load agent!')

            #trade on the trading env
            state = env_instance.reset()
            episode_returns = list()  # the cumulative_return / initial_account
            done = False
            while not done:
                action = model.predict(state)[0]
                state, reward, done, _ = env_instance.step(action)

                total_asset = env_instance.amount + (env_instance.price_ary[env_instance.day] * env_instance.stocks).sum()
                episode_return = total_asset / env_instance.initial_total_asset
                episode_returns.append(episode_return)

            print('episode_return', episode_return)
            print('Test Finished!')   
            return episode_returns

        else:
            raise ValueError('DRL library input is NOT supported yet. Please check.')

    elif mode == 'paper_trading':
        print('Paper trading is NOT supported for now.')
        
    else:
        raise ValueError("Invalid mode input! Please input either 'backtesting' or 'paper_trading'.")
            
if __name__ == '__main__':    
    #fetch data
    from neo_finrl.data_processors.processor_alpaca import AlpacaEngineer as AE
    API_KEY = ""
    API_SECRET = ""
    APCA_API_BASE_URL = 'https://paper-api.alpaca.markets'
    AE = AE(API_KEY,
            API_SECRET,
            APCA_API_BASE_URL)
    stock_list = ['FB',  'AMZN', 'AAPL', 'NFLX', 'GOOG']
    start_date = '2021-01-20'
    end_date = '2021-01-30'
    tech_indicator_list = [
            'macd', 'boll_ub', 'boll_lb', 'rsi_30', 'dx_30',
            'close_30_sma', 'close_60_sma']
    data = AE.data_fetch(stock_list, start_date, end_date, time_interval = '1Min')
    data = AE.clean_data(data)
    print(data)
    data = AE.add_technical_indicators(data)
    print(data)
    data = AE.add_turbulence(data)
    print(data)
    price_ary, tech_ary, turb_ary = AE.df_to_ary(data, tech_indicator_list)
    data_dic = {'price_ary':price_ary, 'tech_ary':tech_ary, 'turbulence_ary':turb_ary}
    
    #construct environment
    from neo_finrl.env_stock_trading.env_stock_alpaca import StockTradingEnv
    env = StockTradingEnv
    
    #demo for elegantrl
    test(data_dic, drl_lib='elegantrl', env=env, agent='ppo', 
    cwd='./test_ppo', net_dimension = 2 ** 9, mode='backtesting')
    
    #demo for rllib 
    test(data_dic, drl_lib='rllib', env=env, agent='ppo', 
    cwd='./test_ppo/checkpoint_000010/checkpoint-10', mode='backtesting')

    #demo for stable baselines3 
    test(data_dic, drl_lib='stable_baselines3', env=env, agent='ppo', 
    cwd='./test_ppo.zip', mode='backtesting')


