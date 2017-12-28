import torch
from src.modules import data_proc, graph, net_misc, envelope
import json
import os
import sys
torch.backends.cudnn.enabled = False




def run(guard):
    outlier_removal_multiplier = 5
    max_history = 500
    base_learning_rate = 0.5
    gradient_multiplier = 1.0
    output = dict()
    if input['mode'] == "forecast":
        local_file = data_proc.get_file(guard.checkpoint_input_path)
        network, state = net_misc.load_checkpoint(local_file)
        if guard.data_path:
            guard.data_path = data_proc.get_frame(guard.data_path)
            guard.data_path = data_proc.process_frames_incremental(guard.data_path, state, outlier_removal_multiplier)

        normal_forecast, raw_forecast, state = net_misc.create_forecasts(guard.data_path, network, state,
                                                                         guard.iterations, guard.forecast_size,
                                                                         guard.io_noise)

        output_env = envelope.create_envelope(normal_forecast, guard.forecast_size, state)
        if guard.graph_save_path:
            graphing_env = envelope.create_envelope(raw_forecast, guard.forecast_size, state)
            graph_path = graph.create_graph(graphing_env, state, guard.forecast_size, guard.io_noise)
            output['saved_graph_path'] = graph.save_graph(graph_path, guard.graph_save_path)
        if guard.checkpoint_output_path:
            output['checkpoint_output_path'] = net_misc.save_model(network, guard.checkpoint_output_path)
        formatted_envelope = envelope.ready_envelope(output_env, state)
        output['envelope'] = formatted_envelope
    if guard.mode == "train":
        guard.data_path = data_proc.get_frame(guard.data_path)
        if guard.checkpoint_input_path:
            local_file = data_proc.get_file(guard.checkpoint_input_path)
            network, state = net_misc.load_checkpoint(local_file)
            data = data_proc.process_frames_incremental(guard.data_path, state, outlier_removal_multiplier)
            lr_rate = net_misc.determine_lr(data, state)
        else:
            data, norm_boundaries, headers = data_proc.process_frames_initial(guard.data_path,
                                                                              outlier_removal_multiplier,
                                                                              beam_width=guard.future_beam_width)
            io_dim = len(norm_boundaries)
            learning_rate = float(base_learning_rate) / io_dim
            network, state = net_misc.initialize_network(io_dim=io_dim, layer_width=guard.layer_width,
                                                         max_history=max_history,
                                                         initial_lr=learning_rate, lr_multiplier=gradient_multiplier,
                                                         io_noise=guard.io_noise,
                                                         attention_beam_width=guard.attention_beam_width,
                                                         future_beam_width=guard.future_beam_width, headers=headers)
            network.initialize_meta(len(data['x']), norm_boundaries)
            lr_rate = state['prime_lr']
        error, network = net_misc.train_autogenerative_model(data_frame=data, network=network,
                                                             checkpoint_state=state, iterations=guard.iterations,
                                                             learning_rate=lr_rate, epochs=guard.epochs,
                                                             drop_percentage=guard.input_dropout)
        output['checkpoint_output_path'] = net_misc.save_model(network, guard.checkpoint_output_path)
        output['final_error'] = float(error)

if __name__ == "__main__":
    input_filename = sys.argv[1]
    output_filename = sys.argv[2]
    with open(input_filename) as f:
        input = json.load(f)
    output = run(input)
    with open(output_filename, 'w') as f:
        json.dump(output, f)
    print('done')