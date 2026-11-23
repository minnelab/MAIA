"""Minimal Triton Python-backend model that echoes its input.

Used as a smoke test to verify that the Triton server is up and serving.
"""
import triton_python_backend_utils as pb_utils


class TritonPythonModel:
    def execute(self, requests):
        responses = []
        for request in requests:
            in0 = pb_utils.get_input_tensor_by_name(request, "INPUT0")
            out0 = pb_utils.Tensor("OUTPUT0", in0.as_numpy())
            responses.append(pb_utils.InferenceResponse(output_tensors=[out0]))
        return responses
